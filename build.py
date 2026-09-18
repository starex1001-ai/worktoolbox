"""Static blog generator compatible with cloudflare_auto.py's content contract."""
import argparse
import json
import re
import shutil
from pathlib import Path
from datetime import date
from html import escape as e
from xml.etree import ElementTree as ET
from content_support import validate_posts, render_body, today

def build(root):
    root=Path(root).resolve()
    config=json.loads((root/'site.json').read_text(encoding='utf-8'))
    posts=json.loads((root/'content/posts.json').read_text(encoding='utf-8'))
    validate_posts(posts,config,root/'public')
    base=config['url'].rstrip('/')
    if not re.fullmatch(r'https://[a-z0-9.-]+',base):
        raise ValueError('Invalid site URL')
    posts=sorted([p for p in posts if p['status']=='published' and p['date']<=today().isoformat()],key=lambda p:(p['date'],p['id']),reverse=True)
    categories={c['slug']:c for c in config['categories']}
    out=root/'dist'
    if out.is_symlink() or out.resolve().parent!=root:
        raise ValueError('Invalid build output path')
    if out.exists(): shutil.rmtree(out)
    out.mkdir()
    shutil.copytree(root/'public',out,dirs_exist_ok=True)
    urls=[]
    def write(name,text):
        p=out/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding='utf-8')
    def listing(p):
        return f'<article class="entry"><div class="entry-meta"><span>{e(categories[p["category"]]["name"])}</span><span>{p["minutes"]}분 읽기</span></div><h3><a href="/posts/{p["slug"]}/">{e(p["title"])}</a></h3><p>{e(p["description"])}</p><div class="entry-bottom"><time datetime="{p["date"]}">{p["date"]}</time><a href="/posts/{p["slug"]}/">읽기 ↗</a></div></article>'
    def page(route,title,description,body,post=None):
        url=base+route
        if route!='/404.html': urls.append((url,post['updated'] if post else None))
        schema={'@context':'https://schema.org','@type':'BlogPosting' if post else 'WebPage','name':title,'url':url,'inLanguage':'ko-KR'}
        if post:
            schema.update(headline=title,description=description,datePublished=post['date'],dateModified=post['updated'],mainEntityOfPage=url,author={'@type':'Organization','name':config['name'],'url':base+'/about/'},publisher={'@type':'Organization','name':config['name'],'url':base})
        data=json.dumps(schema,ensure_ascii=False).replace('<','\\u003c')
        html=f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} | {e(config['name'])}</title><meta name="description" content="{e(description,quote=True)}"><link rel="canonical" href="{url}"><meta name="robots" content="index,follow"><meta property="og:type" content="{'article' if post else 'website'}"><meta property="og:locale" content="ko_KR"><meta property="og:site_name" content="{e(config['name'])}"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(description,quote=True)}"><meta property="og:url" content="{url}"><link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/assets/style.css"><script type="application/ld+json">{data}</script></head><body><a class="skip" href="#main">본문으로 건너뛰기</a><header><div class="header-inner"><a class="brand" href="/"><span class="brand-symbol" aria-hidden="true">{e(config['mark'])}</span><span>{e(config['brand'])}<small>{e(config['name'])}</small></span></a><nav aria-label="주 메뉴"><a href="/#topics">주제별 글</a><a href="/about/">소개</a><a href="/contact/">문의</a></nav></div></header><main id="main">{body}</main><footer><div class="footer-inner"><div><strong>{e(config['name'])}</strong><p>{e(config['tagline'])}</p></div><nav aria-label="하단 메뉴"><a href="/about/">소개</a><a href="/contact/">문의</a><a href="/privacy/">개인정보처리방침</a></nav><small>© {date.today().year} {e(config['name'])}</small></div></footer></body></html>'''
        name='index.html' if route=='/' else route.lstrip('/')+('index.html' if route.endswith('/') else '')
        write(name,html)
    counts={slug:sum(p['category']==slug for p in posts) for slug in categories}
    tabs=''.join(f'<a class="topic" href="/category/{c["slug"]}/"><span class="topic-no">{i+1:02}</span><div><h2>{e(c["name"])}</h2><p>{e(c["description"])}</p></div><span class="topic-count">{counts[c["slug"]]}편 ↗</span></a>' for i,c in enumerate(categories.values()))
    page('/',config['tagline'],config['description'],f'<section class="intro"><div class="intro-label">{e(config["brand"])}</div><h1>{e(config["tagline"])}</h1><p>{e(config["description"])}</p></section><section class="topics" id="topics" aria-label="주제별 가이드">{tabs}</section><section class="reading"><div class="feed"><div class="section-title"><h2>최근 글</h2></div>'+(''.join(listing(p) for p in posts[:12]) or '<p class="empty">첫 글을 준비하고 있습니다.</p>')+'</div></section>')
    for slug,c in categories.items():
        page('/category/'+slug+'/',c['name'],c['description'],f'<section class="page-heading"><span class="kicker">{counts[slug]} ARTICLES</span><h1>{e(c["name"])}</h1><p>{e(c["description"])}</p></section><div class="category-feed">'+(''.join(listing(p) for p in posts if p['category']==slug) or '<p class="empty">이 주제의 글을 준비하고 있습니다.</p>')+'</div>')
    for p in posts:
        if 'body_html' in p:
            toc,sections=render_body(p)
        else:
            toc=''.join(f'<li><a href="#section-{i}">{e(s["heading"])}</a></li>' for i,s in enumerate(p['sections']))
            sections=''.join(f'<section id="section-{i}"><h2>{e(s["heading"])}</h2>'+''.join('<p>'+e(t)+'</p>' for t in s['paragraphs'])+'</section>' for i,s in enumerate(p['sections']))
        related=''.join(f'<a href="/posts/{q["slug"]}/">{e(q["title"])} ↗</a>' for q in posts if q['id']!=p['id'] and q['category']==p['category'])
        body=f'<div class="article-layout"><article class="prose"><div class="breadcrumbs"><a href="/">홈</a> / <a href="/category/{p["category"]}/">{e(categories[p["category"]]["name"])}</a></div><h1>{e(p["title"])}</h1><p class="lead">{e(p["description"])}</p><div class="byline">{e(config["name"])} · <time datetime="{p["date"]}">{p["date"]}</time> · {p["minutes"]}분 읽기</div><p>{e(p["intro"])}</p>{sections}'+(f'<section class="related"><h2>같은 주제의 글</h2>{related}</section>' if related else '')+f'</article><aside class="toc"><strong>이 글의 순서</strong><ol>{toc}</ol><a href="#main">맨 위로 ↑</a></aside></div>'
        page('/posts/'+p['slug']+'/',p['title'],p['description'],body,p)
    page('/about/','소개',config['description'],f'<article class="prose standalone"><span class="kicker">ABOUT</span><h1>{e(config["name"])}</h1><p class="lead">{e(config["description"])}</p><h2>다루는 주제</h2><p>'+e(' · '.join(c['name'] for c in categories.values()))+'</p><h2>작성 원칙</h2><p>일반적인 안내와 직접 확인한 경험을 구분합니다. 바뀔 수 있는 조건과 정보는 해당 서비스의 공식 안내에서 다시 확인할 수 있도록 작성합니다. 잘못된 내용은 제보를 받아 검토하고 수정합니다.</p><h2>광고와 제휴</h2><p>광고나 제휴가 포함된 글은 해당 글에 표시합니다.</p><a href="/contact/">문의하기 ↗</a></article>')
    page('/contact/','문의','콘텐츠 오류 제보 안내입니다.',f'<article class="prose standalone"><span class="kicker">CONTACT</span><h1>콘텐츠 오류 제보</h1><p>관련 글 주소와 수정이 필요한 내용을 공개 문의 게시판에 남길 수 있습니다.</p><a href="{e(config["contact_url"])}">문의 게시판 열기 ↗</a><p>게시판은 GitHub 계정으로 이용하며 작성 내용은 공개됩니다. 이메일, 비밀번호, 인증 코드 등 개인정보나 민감한 내용은 적지 마세요.</p></article>')
    page('/privacy/','개인정보처리방침','사이트와 문의 게시판의 개인정보 처리 안내입니다.',f'<article class="prose standalone"><h1>개인정보처리방침</h1><p>적용일: 2026-09-17</p><h2>사이트 기능</h2><p>이 사이트에는 회원가입, 댓글, 문의 입력 양식이 없습니다. 사이트 코드에 광고나 방문 분석 스크립트, 방문자 정보를 기록하는 쿠키 및 로컬 저장소 기능을 포함하지 않았습니다.</p><h2>호스팅</h2><p>Cloudflare의 페이지 전달 및 보안 과정에서 접속 IP와 요청 정보 등이 처리될 수 있습니다. 자세한 내용은 <a href="https://www.cloudflare.com/privacypolicy/">Cloudflare 개인정보 안내</a>를 참고하세요.</p><h2>외부 문의 게시판</h2><p>문의 게시판은 GitHub에서 제공하며 계정 정보와 작성 내용은 해당 서비스의 정책에 따라 처리됩니다. 게시 내용은 공개되므로 개인정보를 적지 마세요. <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement">GitHub 개인정보 안내</a></p></article>')
    page('/404.html','페이지를 찾을 수 없습니다','주소를 확인해주세요.','<section class="page-heading"><h1>페이지를 찾을 수 없습니다.</h1><a href="/">홈으로 돌아가기</a></section>')
    write('robots.txt',f'User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n')
    tree=ET.Element('urlset',xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    for url,updated in urls:
        item=ET.SubElement(tree,'url'); ET.SubElement(item,'loc').text=url
        if updated: ET.SubElement(item,'lastmod').text=updated
    write('sitemap.xml','<?xml version="1.0" encoding="UTF-8"?>\n'+ET.tostring(tree,encoding='unicode'))
    for file in out.rglob('*.html'):
        html=file.read_text(encoding='utf-8')
        for target in re.findall(r'(?:href|src)="(/[^"#]*)',html):
            dest=out/target.lstrip('/')
            if target.endswith('/'): dest=dest/'index.html'
            if not dest.is_file(): raise ValueError('Missing internal link: '+target)
    print(f'Built {len(urls)+1} pages, {len(posts)} posts: {config["name"]}')

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--site',default=str(Path(__file__).parent)); args=parser.parse_args(); build(args.site)
