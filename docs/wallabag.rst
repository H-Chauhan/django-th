Wallabag
========

Service Description:
--------------------

a self hostable application for saving web pages

modifications of settings.py
----------------------------

1) INSTALLED_APPS :

.. code-block:: python

    INSTALLED_APPS = (
        'th_wallabag',
    )

2) Cache :

After the default cache add :

.. code-block:: python

    CACHES = {
        'default':
        {
            'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': BASE_DIR + '/cache/',
            'TIMEOUT': 600,
            'OPTIONS': {
                'MAX_ENTRIES': 1000
            }
        },
        # Wallabag Cache
        'th_wallabag':
        {
            'TIMEOUT': 500,
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": "redis://127.0.0.1:6379/9",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            }
        },

3) TH_SERVICES

add this line to the TH_SERVICES setting

.. code-block:: python

    TH_SERVICES = (
        'th_wallabag.my_wallabag.ServiceWallabag',
    )



4) The service keys

I strongly recommend that your put the following in a local_settings.py, to avoid to accidentally push this to a public repository


.. code-block:: python

    TH_WALLABAG = {

        'host': 'http://localhost:8080',
        'username': '<user>',
        'password': '<password>',
        'client_id': '<your client id>',
        'client_secret': '<your client secret>'
    }

to fill the parameters, have a look at https://github.com/foxmask/wallabag_api/blob/master/README.rst

creation of the table of the services
-------------------------------------

enter the following command

.. code-block:: bash

    python manage.py migrate


from the admin panel, activation of the service
-----------------------------------------------

from http://yourdomain.com/admin/django_th/servicesactivated/add/

* Select "Wallabag",
* Set the Status to "Enabled"
* Check Auth Required: this will permit to redirect to the user (or you) to your Wallabag application which will request a token
* Fill a description
