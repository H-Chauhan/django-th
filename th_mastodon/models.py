# coding: utf-8
from django.db import models
from django_th.models.services import Services


class Mastodon(Services):
    """
        Model for Mastodon Service
    """
    timeline = models.CharField(max_length=10, default="home")
    tooter = models.CharField(max_length=80, null=True, blank=True)
    fav = models.BooleanField(default=False)
    tag = models.CharField(max_length=80, null=True, blank=True)
    since_id = models.BigIntegerField(null=True, blank=True)
    max_id = models.BigIntegerField(null=True, blank=True)
    count = models.IntegerField(null=True, blank=True)
    trigger = models.ForeignKey('TriggerService')

    class Meta:
        app_label = 'django_th'
        db_table = 'django_th_mastodon'

    def show(self):
        """

        :return: string representing object
        """
        return "Services Mastodon %s %s" % (self.timeline, self.trigger)

    def __str__(self):
        return "%s" % self.timeline
