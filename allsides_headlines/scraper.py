import os
import requests
import json
from bs4 import BeautifulSoup
from tqdm import tqdm

def scrape_story(story_url):
    """scrape a single story"""
    try:
        response = requests.get(story_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, features='lxml')
        sides = soup.select('div.quicktabs-views-group')
        result = {
            'url': story_url,
            'articles': []
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
        raise e
    # print(result)
    return result

def scrape(output_folder='data'):
    page = 0
    results = []
    while True:
        headline_list_url = f'https://www.allsides.com/story/admin?page={page}'
        response = requests.get(headline_list_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, features='lxml')
        table_headers = [el.text.strip() for el in soup.select('table thead th')]
        rows = soup.select('table tbody tr')
        if not rows:
            break
        for row in tqdm(rows, desc=f'Page {page}'):
            line = {}
            fields = row.select('td')
            for k, v in zip(table_headers, fields):
                line[k] = v.text.strip()
            # the first column holds the link to the story
            link = fields[0].select_one('a')['href']
            story_details = scrape_story(f'https://www.allsides.com{link}')

            line = {**line, **story_details}
            # print(line)
            results.append(line)

        page += 1
        # break
    
    if not os.path.isdir(output_folder):
        os.makedirs(output_folder)
    with open(f'{output_folder}/headlines.json', 'w') as f:
        json.dump(results, f, indent=2)

