import simplejson as json
import datetime
from urllib import urlencode
from urllib2 import urlopen, Request
import re

USER_AGENT = ('Mozilla/5.0 (Windows NT 6.1) AppleWebKit/535.7 '
              '(KHTML, like Gecko) Chrome/16.0.912.77 Safari/535.7')

REFERER = 'http://www.nasa.gov/multimedia/videogallery/index.html'

API_URL = 'http://cdn-api.vmixcore.com/apis/media.php'

VIDEO_LANDING_URL = ('http://www.nasa.gov/multimedia/'
                     'videogallery/vmixVideoLanding2.js')

VIDEO_TOPICS = ({'id': '131', 'name': 'All Videos'},
                {'id': '7844', 'name': 'Aeronautics'},
                {'id': '13851', 'name': 'Beyond Earth'},
                {'id': '13861', 'name': 'Commercial Space'},
                {'id': '7845', 'name': 'Earth'},
                {'id': '13841', 'name': 'NASA History and People'},
                {'id': '7914', 'name': 'NASA In Your Life'},
                {'id': '7774', 'name': 'Station and Shuttle'},
                {'id': '7773', 'name': 'Solar System'},
                {'id': '7849', 'name': 'Technology'},
                {'id': '7850', 'name': 'Universe'})

ATOKEN = 'cf15596810c05b64c422e071473549f4'


class Scraper(object):

    def __init__(self, force_refresh=False):
        self.force_refresh = force_refresh
        self.requests = {}
        self.atoken = self.__get_atoken()

    def get_video_topics(self):
        if self.force_refresh:
            url = VIDEO_LANDING_URL
            r_genre_names = re.compile('var genreNames=\[(.+?)\];')
            r_genre_ids = re.compile('var genreIds=\[(.+?)\];')
            html = self.__get_url(url)
            genre_names = re.search(r_genre_names, html).group(1).split(',')
            genre_ids = re.search(r_genre_ids, html).group(1).split(',')
            video_topics = []
            for genre in zip(genre_ids, genre_names):
                video_topics.append({'id': genre[0],
                                     'name': genre[1].strip("'")})
        else:
            video_topics = VIDEO_TOPICS
        return video_topics

    def get_videos_by_topic_id(self, topic_id, start=0, limit=15,
                               order_method=None, order=None):
        if order_method is None or order_method not in ('DESC', 'ASC'):
            order_method = 'DESC'
        if order is None:
            order = 'date_published_start'
        if start < 0:
            start = 0
        if limit < 0 or limit > 250:
            limit = 15
        params = {'action': 'getMediaList',
                  'class_id': 1,
                  'alltime': 1,
                  'order_method': order_method,
                  'order': order,
                  'get_count': 1,
                  'export': 'JSONP',
                  'start': start,
                  'limit': limit,
                  'metadata': 1,
                  'atoken': self.atoken}
        if int(topic_id) < 1000:  # just a guess...
            params['external_genre_ids'] = topic_id
        else:
            params['genre_ids'] = topic_id
        return self.__get_videos(params)

    def search_videos(self, query, fields=None, start=0, limit=15):
        if start < 0:
            start = 0
        if limit < 0 or limit > 250:
            limit = 15
        if fields is None:
            fields = ['title', ]
        params = {'action': 'searchMedia',
                  'class_id': 1,
                  'get_count': 1,
                  'export': 'JSONP',
                  'start': start,
                  'limit': limit,
                  'metadata': 1,
                  'atoken': self.atoken,
                  'fields': ','.join(fields),
                  'query': query}
        return self.__get_videos(params)

    def __get_videos(self, params):
        url = API_URL
        html = self.__get_url(url, get_dict=params)
        json_data = self.__get_json(html)
        if 'media' in json_data:
            items = json_data['media']
        elif 'medias' in json_data:
            items = json_data['medias']['media']
        else:
            items = []
        videos = []
        for item in items:
            if 'genres' in item:
                genres = [g['name'] for g in item['genres']]
            else:
                genres = []
            v = {'title': item['title'],
                 'duration': self.__format_duration(item['duration']),
                 'thumbnail': item['thumbnail'][0]['url'],
                 'description': item['description'],
                 'date': self.__format_date(item['date_published_start']),
                 'filesize': int(item['formats']['format'][-1]['filesize']),
                 'author': item['author'],
                 'genres': genres,
                 'id': item['id']}
            videos.append(v)
        total_count = json_data['total_count']
        return videos, total_count

    def get_video(self, id):
        params = {'action': 'getMedia',
                  'media_id': id,
                  'atoken': self.atoken}
        url = API_URL
        html = self.__get_url(url, get_dict=params)
        json_data = self.__get_json(html)
        media = json_data
        token = media['formats']['format'][-1]['token']
        signature = self.__get_nasa_signature(token)
        timestamp = '1325444582134'
        p = 'token=%s&expires=%s&signature=%s' % (token, timestamp, signature)
        download_url = 'http://media.vmixcore.com/vmixcore/download?%s' % p
        video = {'title': media['title'],
                 'thumbnail': media['thumbnail'][0]['url'],
                 'url': download_url}
        return video

    def __get_nasa_signature(self, token):
        sig_url = ('http://hscripts.vmixcore.com/clients/nasa/'
                   'generate_signature.php?token=%s' % token)
        t = self.__get_url(sig_url)
        r_sig = re.compile('"signature":"(.+?)"')
        signature = re.search(r_sig, t).group(1)
        return signature

    def __get_atoken(self):
        if self.force_refresh:
            url = VIDEO_LANDING_URL
            r_atoken = re.compile('var atoken = \'(.+?)\';')
            html = self.__get_url(url)
            atoken = re.search(r_atoken, html).group(1)
            log('retrieved atoken: %s' % self.atoken)
        else:
            atoken = ATOKEN
        return atoken

    def __get_url(self, url, get_dict='', post_dict=''):
        log('__get_url started with url=%s, get_dict=%s, post_dict=%s'
            % (url, get_dict, post_dict))
        uid = '%s-%s-%s' % (url, urlencode(get_dict), urlencode(post_dict))
        if uid in self.requests.keys():
            log('__get_url using cache for url=%s' % url)
            response = self.requests[uid]
        else:
            if get_dict:
                full_url = '%s?%s' % (url, urlencode(get_dict))
            else:
                full_url = url
            req = Request(full_url)
            req.add_header('User-Agent', USER_AGENT)
            req.add_header('Referer', REFERER)
            log('__get_url opening url=%s' % full_url)
            if post_dict:
                response = urlopen(req, urlencode(post_dict)).read()
            else:
                response = urlopen(req).read()
            self.requests[uid] = response
            log('__get_url finished with %d bytes result' % len(response))
        return response

    def __get_json(self, html):
        log('__get_json started')
        json_obj = json.loads(html)
        log('__get_json finished')
        return json_obj

    def __format_duration(self, seconds_str):
        '''returns 'HH:MM:SS' '''
        return str(datetime.timedelta(seconds=int(seconds_str)))

    def __format_date(self, date_str):
        '''returns 'DD.MM.YYY' '''
        # there is a python/xbmc bug which prevents using datetime twice
        # so doing it ugly :(
        year, month, day = date_str[0:10].split('-')
        return '%s.%s.%s' % (day, month, year)


def log(text):
    print 'Nasa videos scraper: %s' % text