# coding: utf-8
import arrow
from logging import getLogger

from mastodon import Mastodon as MastodonAPI

# django classes
from django.conf import settings
from django.core.cache import caches
from django.shortcuts import reverse
from django.utils import html
from django.utils.translation import ugettext as _

# django_th classes
from django_th.services.services import ServicesMgr
from django_th.models import update_result, UserService
from th_mastodon.models import Mastodon


logger = getLogger('django_th.trigger_happy')

cache = caches['django_th']


class ServiceMastodon(ServicesMgr):
    """
        Service Mastodon
    """
    def __init__(self, token=None, **kwargs):
        super(ServiceMastodon, self).__init__(token, **kwargs)

        self.token = token
        self.service = 'ServiceMastodon'
        self.user = kwargs.get('user')

    def read_data(self, **kwargs):
        """
            get the data from the service

            :param kwargs: contain keyword args : trigger_id at least
            :type kwargs: dict
            :rtype: list
        """
        now = arrow.utcnow().to(settings.TIME_ZONE)
        my_toots = []
        search = {}
        since_id = None
        trigger_id = kwargs['trigger_id']
        date_triggered = arrow.get(kwargs['date_triggered'])

        def _get_toots(toot_obj, search):
            """
                get the toots from mastodon and return the filters to use :
                search and count

                :param toot_obj: from Mastodon model
                :param search: filter used for MastodonAPI.search() or
                twython.get_user_timeline())
                :type toot_obj: Object
                :type search: dict
                :return: count that limit the quantity of tweet to retrieve,
                the filter named search, the tweets
                :rtype: list
            """

            # get the toots for a given tag
            statuses = ''
            count = 100
            if toot_obj.tag:
                count = 100
                search['count'] = count
                search['q'] = toot_obj.tag
                search['result_type'] = 'recent'
                # do a search
                statuses = self.toot_api.search(**search)
                # just return the content of te statuses array
                statuses = statuses['statuses']

            # get the tweets from a given user
            elif toot_obj.tooter:
                count = 200
                search['count'] = count
                search['username'] = toot_obj.tooter

                # call the user timeline and get his toot
                if toot_obj.fav:
                    count = 20
                    search['count'] = 20
                    statuses = self.toot_api.favourites(max_id=max_id,
                                                        since_id=since_id,
                                                        limit=count)
                else:
                    statuses = self.toot_api.account_statuses(
                        id=toot_obj.tooter,
                        max_id=max_id,
                        since_id=since_id,
                        limit=count)

            return count, search, statuses

        if self.token is not None:
            kw = {'model_name': 'Mastodon', 'trigger_id': trigger_id}
            toot_obj = super(ServiceMastodon, self).read_data(**kw)

            if toot_obj.since_id is not None and toot_obj.since_id > 0:
                since_id = toot_obj.since_id
                search = {'since_id': toot_obj.since_id}

            # first request to Mastodon
            count, search, statuses = _get_toots(toot_obj, search)

            if len(statuses) > 0:
                newest = None
                for status in statuses:
                    if newest is None:
                        newest = True
                        # first query ; get the max id
                        search['max_id'] = max_id = status['id']

                since_id = search['since_id'] = statuses[-1]['id'] - 1

                count, search, statuses = _get_toots(toot_obj, search)

                newest = None
                if len(statuses) > 0:
                    my_toots = []
                    for s in statuses:
                        if newest is None:
                            newest = True
                            max_id = s['id'] - 1
                        toot_name = s['account']['username']
                        # get the text of the tweet + url to this one
                        if toot_obj.fav:
                            url = '{0}/api/v1/statuses/{1}'.format(
                                self.api_base_url, s['id'])
                            title = _('Toot Fav from @{}'.format(toot_name))
                        else:
                            url = '{0}/api/v1/accounts/{1}/statuses'.format(
                                self.api_base_url, s['id'])
                            title = _('Toot from @{}'.format(toot_name))
                        # Wed Aug 29 17:12:58 +0000 2012
                        my_date = arrow.get(s['created_at'],
                                            'ddd MMM DD HH:mm:ss Z YYYY')
                        published = arrow.get(my_date).to(settings.TIME_ZONE)
                        if date_triggered is not None and \
                           published is not None and \
                           now >= published >= date_triggered:
                            my_toots.append({'title': title,
                                             'content': s['content'],
                                             'link': url,
                                             'my_date': my_date})
                            # digester
                            self.send_digest_event(trigger_id, title, url)
                    cache.set('th_mastodon_' + str(trigger_id), my_toots)
                    Mastodon.objects.filter(trigger_id=trigger_id).update(
                        since_id=since_id,
                        max_id=max_id,
                        count=count)
        return my_toots

    def save_data(self, trigger_id, **data):
        """
            get the data from the service

            :param trigger_id: id of the trigger
            :params data, dict
            :rtype: dict
        """
        title, content = super(ServiceMastodon, self).save_data(
            trigger_id, **data)

        if self.title_or_content(title):

            content = str("{title} {link}").format(
                title=title, link=data.get('link'))

        content += self.get_tags(trigger_id)

        content = self.set_mastodon_content(content)

        us = UserService.objects.get(user=self.user,
                                     token=self.token,
                                     name='ServiceMastodon')

        try:
            self.toot_api = MastodonAPI(
                client_id=us.client_id,
                client_secret=us.client_secret,
                access_token=self.token,
                api_base_url=us.host
            )
        except ValueError as e:
            logger.error(e)
            update_result(trigger_id, msg=e, status=False)

        try:
            self.toot_api.toot(content)
            status = True
        except Exception as inst:
            logger.critical("Mastodon ERR {}".format(inst))
            update_result(trigger_id, msg=inst, status=False)
            status = False

        return status

    def get_tags(self, trigger_id):
        """
        get the tags if any
        :param trigger_id: the id of the related trigger
        :return: tags string
        """

        # get the Mastodon data of this trigger
        trigger = Mastodon.objects.get(trigger_id=trigger_id)

        tags = ''

        if trigger.tag is not None:
            # is there several tag ?
            tags = ["#" + tag.strip() for tag in trigger.tag.split(',')
                    ] if ',' in trigger.tag else "#" + trigger.tag

            tags = str(','.join(tags)) if isinstance(tags, list) else tags
            tags = ' ' + tags

        return tags

    def set_mastodon_content(self, content):
        """
        cleaning content by removing any existing html tag
        :param content:
        :return:
        """
        content = html.strip_tags(content)

        if len(content) > 560:
            return content[:560]

        return content

    def title_or_content(self, title):
        """
        If the title always contains 'New status from'
        drop the title and get 'the content' instead
        :param title:
        :return:
        """
        if "New status by" in title:
            return False
        return True

    def auth(self, request):
        """
            get the auth of the services
            :param request: contains the current session
            :type request: dict
            :rtype: dict
        """
        # create app
        redirect_uris = '%s://%s%s' % (request.scheme, request.get_host(),
                                       reverse('mastodon_callback'))
        us = UserService.objects.get(user=request.user,
                                     name='ServiceMastodon')
        client_id, client_secret = MastodonAPI.create_app(
            client_name="TriggerHappy", api_base_url=us.host,
            redirect_uris=redirect_uris)

        us.client_id = client_id
        us.client_secret = client_secret
        us.save()

        us = UserService.objects.get(user=request.user,
                                     name='ServiceMastodon')
        # get the token by logging in
        mastodon = MastodonAPI(
            client_id=client_id,
            client_secret=client_secret,
            api_base_url=us.host
        )
        token = mastodon.log_in(username=us.username, password=us.password)
        us.token = token
        us.save()
        return self.callback_url(request)

    def callback_url(self, request):
        us = UserService.objects.get(user=request.user,
                                     name='ServiceMastodon')
        mastodon = MastodonAPI(
            client_id=us.client_id,
            client_secret=us.client_secret,
            access_token=us.token,
            api_base_url=us.host
        )
        redirect_uris = '%s://%s%s' % (request.scheme, request.get_host(),
                                       reverse('mastodon_callback'))
        return mastodon.auth_request_url(redirect_uris=redirect_uris)

    def callback(self, request, **kwargs):
        """
            Called from the Service when the user accept to activate it
            the url to go back after the external service call
            :param request: contains the current session
            :param kwargs: keyword args
            :type request: dict
            :type kwargs: dict
            :rtype: string
        """
        return 'mastodon/callback.html'
