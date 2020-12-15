import json
from tqdm import tqdm
from collections import defaultdict

import snscrape.modules.twitter

search_queries = {
    'left': '(#FromTheLeft) (from:AllSidesNow)',
    'center': '(#FromTheCenter) (from:AllSidesNow)',
    'right': '(#FromTheRight) (from:AllSidesNow)'
}

all_links_hashtag = defaultdict(list)
# TODO RESUME STRATEGY
for bias, query in search_queries.items():
    for i, tweet in enumerate(tqdm(snscrape.modules.twitter.TwitterSearchScraper(query).get_items(), desc='Retrieving from tweets')):
        links = tweet.outlinks
        links = [el for el in links if el.startswith('https://www.allsides.com/') or el.startswith('http://www.allsides.com/')]
        all_links_hashtag[bias].extend(links)
        # Do something
        # if i >= 49: # Stop after the 50th result; enumerate counts from zero
        #     break

with open('data/tweet_links_by_bias_hashtag.json', 'w') as f:
    json.dump(all_links_hashtag, f, indent=2)

all_links = []
query_all = 'from:AllSidesNow'
for i, tweet in enumerate(tqdm(snscrape.modules.twitter.TwitterSearchScraper(query_all).get_items(), desc='Retrieving from tweets')):
    links = tweet.outlinks
    links = [el for el in links if el.startswith('https://www.allsides.com/') or el.startswith('http://www.allsides.com/')]
    all_links.extend(links)

with open('data/tweet_links.json', 'w') as f:
    json.dump(all_links_hashtag, f, indent=2)
