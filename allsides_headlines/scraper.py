import os
import json
import time
import requests
import html2markdown
from bs4 import BeautifulSoup
from tqdm import tqdm
from lxml import html
from lxml.html import clean
from multiprocessing.pool import ThreadPool

cleaner = clean.Cleaner()
cleaner.safe_attrs_only = True
cleaner.safe_attrs=frozenset(['href', 'src']) # href for a, src for img

def preprocess_dom_node_for_markdown(dom_node):
    tree = html.fromstring(str(dom_node))
    cleaned = cleaner.clean_html(tree)
    # get children (not the enclosing div element)
    children = list(cleaned)
    cleaned_strs = [html.tostring(el).decode('utf-8') for el in children]
    result = ''.join(cleaned_strs)
    return result

def scrape_story(story_url, retries=5):
    """scrape a single story"""
    if retries < 1:
        raise ValueError('Not enough retries available')
    try:
        response = requests.get(story_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, features='lxml')
        sides = soup.select('div.quicktabs-views-group')
        description = soup.select_one('div.story-id-page-description')
        descr_string = preprocess_dom_node_for_markdown(description)
        markdown_description = html2markdown.convert(descr_string)
        result = {
            'url': story_url,
            'articles': [],
            'description': markdown_description
        }
        for side in sides:
            source_bias = side.select_one('div.bias-image img')
            # some don't have the source e.g. https://www.allsides.com/story/gop-tax-plan
            if source_bias:
                source_bias = source_bias['title'].split(':')[-1].strip()
            source = side.select_one('div.news-source')
            source_name = source.text.strip()
            source_evaluation_url = source.parent['href']
            article_url = side.select_one('div.read-more-story a')['href']
            article_title = side.select_one('div.news-title').text.strip()
            body = side.select_one('div.news-body')
            body_truncated = body.text.strip()
            spans = body.select('span')
            has_span = True if spans else False
            if has_span:
                content_category = spans[0].text.strip()
                body_truncated = body_truncated.replace(content_category, '', 1).strip()
            else:
                content_category = 'NEWS'
            
            result['articles'].append({
                'source': source_name,
                'source_evaluation_url': source_evaluation_url,
                'bias': source_bias,
                'url': article_url,
                'title': article_title,
                'body_truncated': body_truncated,
                'content_category': content_category
            })
    except Exception as e:
        print(story_url)
        print(f'waiting some time because of {e}')
        time.sleep(10)
        print(f'retrying url {story_url}')
        return scrape_story(story_url, retries=retries-1)
    # print(result)
    return result

def process_row(row, table_headers):
    line = {}
    fields = row.select('td')
    for k, v in zip(table_headers, fields):
        line[k] = v.text.strip()
    # the first column holds the link to the story
    link = fields[0].select_one('a')['href']
    story_details = scrape_story(f'https://www.allsides.com{link}')

    line = {**line, **story_details}
    return line

def scrape_headlines(output_folder):
    file_path = f'{output_folder}/headlines.json'
    
    # load headlines if they have already been scraped
    prev_results = []
    if not os.path.isdir(output_folder):
        os.makedirs(output_folder)
    if os.path.isfile(file_path):
        with open(file_path) as f:
            prev_results = json.load(f)
    
    new_results = []
    page = 0
    stop = False
    while not stop:
        headline_list_url = f'https://www.allsides.com/story/admin?page={page}'
        response = requests.get(headline_list_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, features='lxml')
        table_headers = [el.text.strip() for el in soup.select('table thead th')]
        rows = soup.select('table tbody tr')
        if not rows:
            break
        wrapper = lambda row: process_row(row, table_headers)
        with ThreadPool(8) as pool:
            for line in tqdm(pool.imap(wrapper, rows), total=len(rows), desc=f'Page {page}'):
                # print(line['url'])

                if any(el['url'] == line['url'] for el in prev_results):
                    print('found', line['url'], ': terminating now')
                    stop = True
                    break
                else:
                    new_results.append(line)

        page += 1


    # keep the order
    results = new_results + prev_results
    with open(f'{output_folder}/headlines.json', 'w') as f:
        json.dump(results, f, indent=2)

def scrape_biases(output_folder):
    # 800+ sources --> 50 per page --> pages: 16+ --> 30 pages (with also unrated sources)
    # https://www.allsides.com/media-bias/media-bias-ratings?page=1&field_featured_bias_rating_value=All&field_news_source_type_tid%5B1%5D=1&field_news_source_type_tid%5B2%5D=2&field_news_source_type_tid%5B3%5D=3&field_news_source_type_tid%5B4%5D=4&field_news_bias_nid_1%5B1%5D=1&field_news_bias_nid_1%5B2%5D=2&field_news_bias_nid_1%5B3%5D=3&field_news_bias_nid_1%5B4%5D=4&title=

    # TODO double check why nodes collection has 1643 sources, and this one only 1506
    results = []
    page = 0
    stop = False
    while not stop:
        print('sources page', page)
        params = {
            'page': page,
            'field_featured_bias_rating_value': 'All', # All or featured
            'field_news_source_type_tid[1]': '1', # Type: Author
            'field_news_source_type_tid[2]': '2', # Type: News Media
            'field_news_source_type_tid[3]': '3', # Type: Think Tank / Policy Group
            'field_news_source_type_tid[4]': '4', # Type: Reference
            'field_news_bias_nid_1[1]': '1', # Bias Rating: Left
            'field_news_bias_nid_1[2]': '2', # Bias Rating: Center or Mixed
            'field_news_bias_nid_1[3]': '3', # Bias Rating: Right
            'field_news_bias_nid_1[4]': '4', # Bias Rating: Not Rated
        }
        res = requests.get('https://www.allsides.com/media-bias/media-bias-ratings', params=params)
        res.raise_for_status()

        text = res.text
        soup = BeautifulSoup(text, features='lxml')

        headers = [el.text.strip() for el in soup.select('table thead tr th')]
        
        rows = soup.select('table tbody tr')
        if not rows:
            break
        for r in rows:
            fields = r.select('td')
            source_name = fields[0].text.strip()
            source_details_url = fields[0].select_one('a')
            if not source_details_url:
                stop = True
                break
            source_details_url = source_details_url['href']
            source_details_url = f'https://www.allsides.com{source_details_url}'
            bias_label = fields[1].select_one('a')['href'].split('/')[-1]
            agree_cnt = int(fields[3].select_one('.agree').text.strip())
            disagree_cnt = int(fields[3].select_one('.disagree').text.strip())
            results.append({
                'name': source_name,
                'details_url': source_details_url,
                'bias_label': bias_label,
                'agree_cnt': agree_cnt,
                'disagree_cnt': disagree_cnt
            })
        page += 1

    results = results

    for row in tqdm(results, desc='collecting details'):
        try:
            scrape_source_node(row)
        except Exception as e:
            print(row['details_url'])
            raise e
    
    with open(f'{output_folder}/sources.json', 'w') as f:
        json.dump(results, f, indent=2)
    return results

def scrape_source_node(row):
    node_url = row['details_url']

    res = requests.get(node_url)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, features='lxml')
    source_type = soup.select_one('div.latest_news_source p').text.strip()

    homepage = description = owner = None
    links = []
    side_panel = soup.select_one('div.dynamic-grid')
    if side_panel:
        homepage = side_panel.select_one('a')['href']
        text_descr = side_panel.select_one('div.grid-text-height')
        if text_descr:
            description = text_descr.select_one('p.more').text.strip()
            owner = [el.text for el in text_descr.select('p')]
            owner = [el.replace('Owned By:', '').strip() for el in owner if 'Owned By:' in el]
            if owner:
                owner = owner[0]
            else:
                owner = None
        links = side_panel.select('ul li a')
        links = [el['href'] for el in links]

    # ratings: {'name': {'value': true/false/Low/Medium/High, 'detail: TEXT}}
    ratings_els = soup.select('div.news-source-full-area ul.b-list li')
    ratings = {}
    for r in ratings_els:
        rating_name = ''.join(r.find_all(text=True, recursive=False)).replace('"', '').replace(':', '').strip()
        detail = r.select_one('span').text.strip()
        if 'checked0' in r['class']:
            value = False
        elif 'checked1' in r['class']:
            value = True
        else:
            value = rating_name
            rating_name = 'confidence'
            detail = r.text.strip()
        ratings[rating_name] = {
            'value': value,
            'detail': detail
        }
    # TODO community feedback is always false, is there some JS? ::before?

    # full description of the bias
    evaluation_details = soup.select_one('div.field-items div')
    evaluation_details_html = preprocess_dom_node_for_markdown(evaluation_details)
    evaluation_details_markdown = html2markdown.convert(evaluation_details_html)

    # extend result
    row['homepage'] = homepage
    row['links'] = links
    row['source_type'] = source_type
    row['description'] = description
    row['owner'] = owner
    row['ratings'] = ratings
    row['evaluation_details'] = evaluation_details_markdown



def scrape(output_folder='data'):
    scrape_headlines(output_folder)
    scrape_biases(output_folder)
