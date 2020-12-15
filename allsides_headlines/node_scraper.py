import os
import requests
import json
from collections import defaultdict
from bs4 import BeautifulSoup
from tqdm import tqdm
from multiprocessing.pool import ThreadPool


max_node_id = 114000   # 113140
# TODO: detect the end, based on last known existing ID and then finding a range where everything is 404
nodes_cache_path = 'data/nodes_cache.json'

def get_node(node_id):
    result = {'id': node_id}
    try:
        node_url = f'https://www.allsides.com/node/{node_id}'
        res = requests.get(node_url, allow_redirects=False)
        #headers={
        #    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
        #})
        if res.status_code == 404:
            return result
        res.raise_for_status()
        # follow 1 redirect
        location = res.headers['location']
        if location != node_url:
            res2 = requests.get(location, allow_redirects=False)
            if res2.status_code == 404:
                return result
            res2.raise_for_status()
            result['html'] = res2.text
            result['canonical_url'] = location
    except Exception as e:
        print('node', node_id, 'produced', e)
    return result

def parse_news_item(raw_html, url):
    soup = BeautifulSoup(raw_html, features='lxml')
    #
    source = soup.select_one('div.article-publication span.field-content a')
    if source:
        source_name = source.text.strip()
        source_evaluation_url = source['href']
    else:
        source_name = None
        source_evaluation_url = None
    bias = soup.select_one('span.media-bias-name span.field-content a')
    if bias:
        bias_name = bias.text.strip()
        bias_url = bias['href']
    else:
        bias_name = None
        bias_url = None
    title = soup.select_one('div.article-name')
    if title:
        title = title.text.strip()
    body = soup.select_one('div.article-description')
    if body:
        article_description = body.text.strip()
        spans = body.select('span.opinion')
    else:
        article_description = None
        spans = None
    article_url = soup.select_one('div.read-more-story a')
    if article_url:
        article_url = article_url['href']
    topic = soup.select_one('div.article-topic-name a')
    if topic:
        # print(3)
        topic_name = topic.text.strip()
        # print(4)
        topic_url = topic['href']
        # print(5)
    else:
        topic_name = None,
        topic_url = None
    #
    
    has_span = True if spans else False
    if has_span:
        content_category = spans[0].text.strip()
        article_description = article_description.replace(content_category, '', 1).strip()
    else:
        content_category = 'NEWS'
    #
    posted_date = soup.select_one('div.article-posted-date')
    if posted_date:
        posted_date = posted_date.text.replace('Posted on AllSides', '').strip()
    #
    return {
        'allsides_url': url,
        'article_url': article_url,
        'title': title,
        'description': article_description,
        'source': source_name,
        'source_evaluation_url': source_evaluation_url,
        'bias': bias_name,
        'bias_url': bias_url,
        'content_category': content_category,
        'topic': topic_name,
        'topic_url': topic_url,
        'posted_date': posted_date
    }

def cached_get_node(node_cache, node_id):
    if node_id in node_cache['nodes']:
        # already cached
        return node_cache['nodes'][node_id]
    else:
        if node_id < node_cache['max_id']:
            # empty, no need to check again
            return {'id': node_id}
        else:
            # go and get it
            node = get_node(node_id)
            # then save to cache
            node_cache['nodes'][node_id] = node
            return node



# load already downloaded nodes
if os.path.isfile(nodes_cache_path):
    with open(nodes_cache_path) as f:
        node_cache = json.load(f)
else:
    node_cache = {
        'nodes': {},
        'max_id': 0
    }

# TODO manually repeat errored nodes for connection 
# missing_nodes_ids = [19688, 26283, 66202, 78461, 78477, 78450, 78458, 78459, 78454, 78426, 83232, 83236, 83241, 109882, 109876, 109919]
# missing_nodes = [get_node(el) for el in missing_nodes_ids]
# TODO manually put the scraped things into the node_cache, update max_id:
# nodes_by_id = {el['id']: el for el in sorted(nodes + missing_nodes, key=lambda el:el['id'])}
# max_id = max(nodes_by_id.keys())
# node_cache = {'nodes': nodes_by_id, 'max_id': max_id}
# TODO
# without 'location': 31296 31365 31427 31465 31620 31725 31801 31798 31812 31826 31911 32132 32141 32237 32426 32467 32546
# 32669 32802 32869 32974 33003
nodes = []
node_possible_ids = range(max_node_id)
node_id = 0
get_node_wrap = lambda node_id: cached_get_node(node_cache, node_id)
with ThreadPool(32) as pool:
    for node in tqdm(pool.imap(get_node_wrap, node_possible_ids), total=max_node_id, desc=f'Getting nodes'):
        if 'canonical_url' in node:
            nodes.append(node)

with open(nodes_cache_path, 'w') as f: # 9.25GB
    json.dump(nodes, f, indent=2)


# divide into categories of URLs
urls_by_group = defaultdict(list)
for node in tqdm(nodes, desc='dividing urls into groups'):
    url = node['canonical_url']
    marker_start = 'https://www.allsides.com/'
    if not marker_start in url:
        continue
        #raise ValueError(url)
    path = url.replace(marker_start, '')
    path_parts = path.split('/')
    group = path_parts[0]
    urls_by_group[group].append(url)

with open('data/nodes_by_group.json', 'w') as f:
    json.dump(urls_by_group, f, indent=2)

# parse content of the news nodes (73839 news nodes)
nodes_by_url = {node['canonical_url']: node for node in nodes} # 76441

news = []
for url in tqdm(urls_by_group['news'], desc='parsing news items'):
    # TODO resume or retrieve again html from URL?
    node = nodes_by_url[url]
    node_id = node['id']
    raw_html = node['html']
    news_item = parse_news_item(raw_html, url)
    news_item['node_id'] = node_id
    news.append(news_item)


# filtering
# deduped = {el['allsides_url']: el for el in news}.values() ### useless, they change url after /news/
news_cleaned = [el for el in news if el['article_url']]
with open('data/news_nodes.json', 'w') as f:
    json.dump(news_cleaned, f, indent=2)

# USELESS
by_article_url = defaultdict(list)
for el in news_cleaned:
    by_article_url[el['article_url']].append(el)

duplicate_article_url = [el for el in by_article_url.values() if len(el) > 1]
len(duplicate_article_url) # 880