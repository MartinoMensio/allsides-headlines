import os
import json
import time
import requests
import html2markdown
from bs4 import BeautifulSoup
from tqdm import tqdm
from multiprocessing.pool import ThreadPool

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
        descr_string = ''.join([str(x) for x in description.contents]).replace('target="_blank"', '').replace('target="blank"', '').replace('rel="nofollow"', '')
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
            source = side.select_one('div.news-source').text.strip()
            article_url = side.select_one('div.read-more-story a')['href']
            result['articles'].append({
                'source': source,
                'bias': source_bias,
                'url': article_url
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
        pool = ThreadPool(8)
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
    # TODO scrape detail page, where there is a link to the source homepage 
    results = []
    page = 0
    stop = False
    while not stop:
        print('page', page)
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

    # 800+ sources --> 50 per page --> pages: 16+ --> 30 pages (with also unrated sources)
    # https://www.allsides.com/media-bias/media-bias-ratings?page=1&field_featured_bias_rating_value=All&field_news_source_type_tid%5B1%5D=1&field_news_source_type_tid%5B2%5D=2&field_news_source_type_tid%5B3%5D=3&field_news_source_type_tid%5B4%5D=4&field_news_bias_nid_1%5B1%5D=1&field_news_bias_nid_1%5B2%5D=2&field_news_bias_nid_1%5B3%5D=3&field_news_bias_nid_1%5B4%5D=4&title=

    with open(f'{output_folder}/sources.json', 'w') as f:
        json.dump(results, f, indent=2)


def scrape(output_folder='data'):
    scrape_headlines(output_folder)
    # scrape_biases(output_folder)