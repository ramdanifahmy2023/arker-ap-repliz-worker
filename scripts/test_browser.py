"""Browser acceptance against an isolated, unpublished Arker fixture runtime.

The credentials JSON is read only into memory. Screenshots carry a fixture label.
Requires the root development environment with Playwright and Chromium installed.
"""
from __future__ import annotations
import argparse
import json
import time
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

MENUS = {
    'overview':'Ringkasan','flow':'Peta alur','worker':'Kendali worker','attention':'Perlu perhatian',
    'intake':'Tambah konten','queue':'Batch & antrean','bank':'Bank konten','detail':'Detail & preview',
    'accounts':'Akun sosial','quota':'Rotasi & kuota','calendar':'Kalender posting','published':'Hasil publikasi',
    'video':'Pengolahan video & AI','personas':'Persona & caption','comments':'Komentar & balasan',
    'reports':'Laporan & statistik','connections':'Koneksi layanan','telegram':'Telegram & notifikasi',
    'storage':'Penyimpanan & cleanup','backups':'Backup & pemulihan','activity':'Riwayat aktivitas',
    'settings':'Pengaturan & akses',
}

def seed_fixture(data_dir: Path):
    from arker.db import Store
    if '.artifacts' not in data_dir.parts:
        raise ValueError('Browser fixtures require a private .artifacts directory.')
    store = Store(data_dir)
    if store.configuration()['config']['application']['publish_enabled']:
        raise ValueError('Fixture runtime must have publication disabled.')
    stamp = time.time()
    with store.connect() as db:
        if db.execute("SELECT COUNT(*) FROM assets WHERE id LIKE 'browser-fixture-%'").fetchone()[0]:
            return
        db.execute('INSERT INTO batches VALUES (?,?,?,?)',('browser-fixture-batch','fixture',1000,stamp))
        for i in range(1000):
            identifier=f'browser-fixture-{i:04d}'
            stage=['download','inspect','draft','render','drive','delivery'][i%6]
            state='preview_ready' if i%4==0 else 'published' if i%4==1 else 'held'
            context=json.dumps({'fixture':True,'facts':['Video buatan untuk pemeriksaan antarmuka.']})
            db.execute('INSERT INTO assets(id,batch_id,source_url,source_username,source_verified,state,stage,progress,total,config_version,context,hook,caption,error,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(identifier,'browser-fixture-batch',f'https://www.instagram.com/reel/ARKERFIXTURE{i:04d}/','fixture_source',1,state,stage,32+i%60 if i%6==3 else None,100 if i%6==3 else None,1,context,f'Konten fixture {i+1:04d}','Caption fixture untuk pengujian tampilan.','Fixture ditahan; tidak boleh dikirim.' if state=='held' else None,stamp-(i%7)*86400-(i%20)*60,stamp-(i%30)*60))
            for platform in ('tiktok','facebook','youtube'):
                dstate='published' if state=='published' else 'shadow'
                db.execute('INSERT INTO deliveries(id,asset_id,platform,state,created_at,updated_at,published_at) VALUES (?,?,?,?,?,?,?)',(f'{identifier}-{platform}',identifier,platform,dstate,stamp,stamp,stamp-(i%7)*86400 if dstate=='published' else None))
        for stage in ('download','inspect','draft','render','drive'):
            store_payload=json.dumps({'stage':stage,'duration_seconds':5+len(stage),'fixture':True})
            db.execute('INSERT INTO events(kind,entity_id,payload,created_at) VALUES (?,?,?,?)',('asset.stage','browser-fixture-0000',store_payload,stamp))
    store.event('fixture.browser_seeded', payload={'assets':1000,'publication':False})


def lifecycle_review(args):
    credentials=json.loads(args.credentials.read_text())
    args.output.mkdir(parents=True,exist_ok=True)
    checks=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.goto(args.base_url+'/#worker')
        page.locator('input[type=email]').fill(credentials['email'])
        page.locator('input[type=password]').fill(credentials['password'])
        page.get_by_role('button',name='Masuk ke panel').click()
        page.get_by_role('heading',name='Proses layanan',exact=True).wait_for()
        page.wait_for_timeout(700)
        if page.get_by_role('button',name='Jalankan worker',exact=True).is_enabled():
            page.get_by_role('button',name='Jalankan worker',exact=True).click()
        expect(page.get_by_role('button',name='Hentikan worker',exact=True)).to_be_enabled(timeout=25000)
        page.get_by_role('button',name='Hentikan worker',exact=True).click()
        expect(page.get_by_role('status').filter(has_text='Proses worker sudah berhenti.')).to_be_visible(timeout=25000)
        expect(page.get_by_role('button',name='Jalankan worker',exact=True)).to_be_enabled()
        checks.append('stop_worker_keeps_api_and_panel_alive')
        page.get_by_role('button',name='Jalankan worker',exact=True).click()
        expect(page.get_by_role('status').filter(has_text='Proses worker sudah berjalan.')).to_be_visible(timeout=25000)
        checks.append('start_worker_confirmed_by_owned_process')
        page.get_by_role('button',name='Restart worker',exact=True).click()
        expect(page.get_by_role('status').filter(has_text='Worker sudah berjalan dengan proses baru.')).to_be_visible(timeout=25000)
        checks.append('restart_confirmed_by_new_worker_pid')
        page.goto(args.base_url+'/#settings')
        page.get_by_label('Maksimal link per batch',exact=True).fill('97')
        page.get_by_role('button',name='Periksa perubahan').click()
        page.get_by_role('button',name='Simpan versi baru').click()
        expect(page.get_by_text('Worker sudah mengonfirmasi versi ini.',exact=True)).to_be_visible(timeout=25000)
        checks.append('saved_configuration_applied_acknowledged_by_worker')
        page.goto(args.base_url+'/#worker')
        page.get_by_role('button',name='Jeda pemrosesan',exact=True).click()
        expect(page.locator('.action-result').filter(has_text='Selesai')).to_be_visible(timeout=25000)
        checks.append('pause_command_acknowledged')
        browser.close()
    report={'fixture':True,'publication':False,'passed':True,'checks':checks}
    (args.output/'lifecycle-report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'passed':True,'lifecycle_checks':len(checks)}))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--credentials',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seed-data-dir',type=Path)
    parser.add_argument('--preview-video',type=Path)
    parser.add_argument('--lifecycle-only',action='store_true')
    args=parser.parse_args()
    if args.lifecycle_only:
        return lifecycle_review(args)
    if args.seed_data_dir:
        seed_fixture(args.seed_data_dir.resolve())
    if args.preview_video and args.seed_data_dir:
        from arker.db import Store
        data_dir=args.seed_data_dir.resolve()
        if '.artifacts' not in data_dir.parts: raise ValueError('Fixture runtime required.')
        media=data_dir/'cache'/'browser-preview.mp4';media.parent.mkdir(exist_ok=True)
        shutil.copyfile(args.preview_video,media)
        store=Store(data_dir)
        with store.connect() as db:
            db.execute('INSERT OR REPLACE INTO artifacts(id,asset_id,kind,path,size,created_at) VALUES (?,?,?,?,?,?)',('browser-fixture-preview','browser-fixture-0000','rendered',str(media),media.stat().st_size,time.time()))
    credentials=json.loads(args.credentials.read_text())
    args.output.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1]
    axe=root/'apps/web/node_modules/axe-core/axe.min.js'
    result={'fixture':True,'publication':False,'menu_count':22,'checks':[],'axe':[],'screenshots':[]}
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(viewport={'width':1440,'height':1000},color_scheme='light',reduced_motion='no-preference',bypass_csp=True)
        page=context.new_page()
        errors=[]
        page.on('pageerror',lambda exc: errors.append(type(exc).__name__))
        page.goto(args.base_url)
        expect(page.locator('input[type=email]')).to_be_visible()
        page.keyboard.press('Tab')
        assert page.locator(':focus').count()==1
        page.locator('input[type=email]').fill(credentials['email'])
        page.locator('input[type=password]').fill(credentials['password'])
        page.get_by_role('button',name='Masuk ke panel').click()
        expect(page.get_by_role('heading',name='Ringkasan',exact=True)).to_be_visible()
        result['checks'].append('email_password_login')
        def settle():
            page.wait_for_timeout(200)
            page.locator('.loading').first.wait_for(state='hidden',timeout=10000) if page.locator('.loading').count() else None
        def screenshot(name):
            page.wait_for_timeout(350)
            page.evaluate("""() => {let n=document.getElementById('fixture-label');if(!n){n=document.createElement('div');n.id='fixture-label';n.style='position:fixed;bottom:10px;right:12px;z-index:99;background:#f9edcc;color:#563d08;border:1px solid #795910;padding:6px 10px;border-radius:5px;font:12px system-ui';n.textContent='Fixture pengujian · tidak ada publikasi';document.body.append(n)}}""")
            page.screenshot(path=str(args.output/name),full_page=True)
            result['screenshots'].append(name)
        def audit(name):
            page.add_script_tag(path=str(axe))
            findings=page.evaluate("async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}});return r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))}")
            result['axe'].append({'view':name,'violations':findings})
        for route,title in MENUS.items():
            start=time.perf_counter()
            page.goto(args.base_url+'/#'+route)
            expect(page.get_by_role('heading',level=1,name=title,exact=True)).to_be_visible()
            settle()
            assert not page.get_by_text('Halaman tidak dapat ditampilkan').count(),route
            assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'),route
            result['checks'].append({'menu':route,'seconds':round(time.perf_counter()-start,3)})
        if args.preview_video:
            page.goto(args.base_url+'/#detail?id=browser-fixture-0000');settle()
            page.locator('video').evaluate('(video)=>{video.currentTime=1;}')
            page.wait_for_timeout(400)
            assert page.locator('video').evaluate('(video)=>video.videoWidth')>0
            screenshot('detail-fixture-preview.png');audit('detail-preview')
            result['checks'].append('authenticated_real_media_preview')
        page.goto(args.base_url+'/#overview');settle();screenshot('overview-fixture-light.png');audit('overview-light')
        page.get_by_role('button',name='Gunakan tema gelap').click();screenshot('overview-fixture-dark.png');audit('overview-dark')
        page.get_by_role('button',name='Kurangi animasi').click()
        assert page.locator('html').get_attribute('data-motion')=='reduced'
        result['checks'].append('reduced_motion_control')
        page.get_by_role('button',name='Gunakan tema terang').click()
        page.goto(args.base_url+'/#storage');settle();screenshot('storage-fixture-light.png');audit('storage-light')
        field=page.get_by_label('Link folder Google Drive',exact=True)
        field.fill('https://example.com/private')
        page.get_by_role('button',name='Periksa lokasi & link').click()
        expect(page.get_by_text('Lokasi atau link perlu diperbaiki')).to_be_visible()
        result['checks'].append('storage_arbitrary_url_rejected')
        page.goto(args.base_url+'/#settings');settle()
        page.get_by_label('Maksimal link per batch',exact=True).fill('99')
        page.get_by_role('button',name='Periksa perubahan').click()
        page.get_by_role('button',name='Simpan versi baru').click()
        expect(page.get_by_text('Penyimpanan dan penerapan mempunyai status terpisah.')).to_be_visible()
        result['checks'].append('configuration_saved_pending_worker')
        page.goto(args.base_url+'/#connections');settle()
        page.get_by_label('Access Key baru',exact=True).fill('browser-fixture-access')
        page.get_by_label('Secret Key baru',exact=True).fill('browser-fixture-secret')
        page.get_by_role('button',name='Simpan kredensial').first.click()
        expect(page.get_by_label('Secret Key baru',exact=True)).to_have_value('')
        body=page.locator('body').inner_text()
        assert 'browser-fixture-secret' not in body
        stored=page.evaluate('JSON.stringify(localStorage)')
        assert 'browser-fixture-secret' not in stored
        result['checks'].append('credential_write_only_and_cleared')
        page.goto(args.base_url+'/#intake');settle()
        page.get_by_label('Link sumber',exact=True).fill('https://example.com/invalid')
        page.get_by_role('button',name='Periksa & masukkan antrean').click()
        expect(page.get_by_text('Hasil penerimaan')).to_be_visible()
        result['checks'].append('invalid_source_rejected')
        page.goto(args.base_url+'/#queue');settle()
        assert page.locator('tbody tr').count()<=50
        result['checks'].append('1000_assets_paginated')
        page.set_viewport_size({'width':360,'height':800})
        for route in ['overview','queue','connections','storage','flow']:
            page.goto(args.base_url+'/#'+route);settle()
            assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth'),route
            screenshot(f'{route}-fixture-mobile.png')
            if route in ('overview','storage'): audit(route+'-mobile')
        page.get_by_role('button',name='Buka navigasi').click()
        expect(page.get_by_role('link',name='Pengaturan & akses',exact=True)).to_be_visible()
        page.get_by_role('link',name='Pengaturan & akses',exact=True).click()
        expect(page.locator('.sidebar')).not_to_have_class('sidebar open')
        result['checks'].append('mobile_navigation')
        page.set_viewport_size({'width':768,'height':1000})
        page.goto(args.base_url+'/#storage');settle()
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        screenshot('storage-fixture-tablet.png')
        page.set_viewport_size({'width':1440,'height':1000})
        page.goto(args.base_url+'/#overview');settle()
        page.set_viewport_size({'width':720,'height':500})
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        screenshot('overview-fixture-zoom200.png')
        result['checks'].append('zoom_200_css_viewport_emulation_no_overflow')
        page.set_viewport_size({'width':1440,'height':1000})
        page.route('**/api/health',lambda route: route.abort())
        page.get_by_role('button',name='Perbarui data',exact=True).click()
        expect(page.get_by_role('alert').filter(has_text='Layanan kontrol')).to_be_visible()
        assert page.locator('.app').get_attribute('data-idle')=='true'
        result['checks'].append('offline_data_not_presented_as_live')
        result['page_errors']=errors
        result['passed']=not errors and all(not v['violations'] for v in result['axe'])
        context.close();browser.close()
    (args.output/'report.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'passed':result['passed'],'checks':len(result['checks']),'axe_violations':sum(len(a['violations']) for a in result['axe']),'page_errors':len(result['page_errors'])}))
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
