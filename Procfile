release: python manage.py migrate
web: waitress-serve --port=$PORT settings.wsgi:application
infobot: python manage.py run_info_bot
worker: REMAP_SIGTERM=SIGQUIT celery --app=taskapp worker --loglevel=debug --without-heartbeat --without-gossip
beat: celery --app=taskapp beat --max-interval=5