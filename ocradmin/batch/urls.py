from django.conf.urls.defaults import *

urlpatterns = patterns('',
    (r'^abort_batch/(?P<batch_pk>\d+)/?$', 'ocradmin.batch.views.abort_batch'),
	(r'^create/?$', 'ocradmin.batch.views.create'),
	(r'^delete/(?P<batch_pk>\d+)/?$', 'ocradmin.batch.views.delete'),
	(r'^export_options/(?P<batch_pk>\d+)/?$', 'ocradmin.batch.views.export_options'),
	(r'^export/(?P<batch_pk>\d+)/?$', 'ocradmin.batch.views.export'),
	(r'^latest/?$', 'ocradmin.batch.views.latest'),
	(r'^list/?$', 'ocradmin.batch.views.list'),
	(r'^new/?$', 'ocradmin.batch.views.new'),
    (r'^results/(?P<batch_pk>\d+)/?$', 'ocradmin.batch.views.results'),
    (r'^results/(?P<batch_pk>\d+)/(?P<page_index>\d+)/?$', 'ocradmin.batch.views.page_results'),
    (r'^save/(?P<batch_pk>\d+)/(?P<page_index>\d+)/?$', 'ocradmin.batch.views.save_page_data'),
    (r'^retry/(?P<batch_pk>\d+)/?$', 'ocradmin.batch.views.retry'),
    (r'^retry_errored/(?P<batch_pk>\d+)/?$', 'ocradmin.batch.views.retry_errored'),
    (r'^show/(?P<batch_pk>\d+)/?$', 'ocradmin.batch.views.show'),
	(r'^spellcheck/?$', 'ocradmin.batch.views.spellcheck'),
    (r'^transcript/(?P<batch_pk>\d+)/?$', 'ocradmin.batch.views.transcript'),
    (r'^test/?$', 'ocradmin.batch.views.test'),
	(r'^upload_files/?$', 'ocradmin.batch.views.upload_files'),
)
