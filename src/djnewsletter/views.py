import json
from datetime import datetime

from django.http import HttpResponse, Http404, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

from djnewsletter.models import Bounced


@csrf_exempt
def create_sendgrid_bounced(request):
    if request.method != 'POST':
        raise Http404

    data = request.body
    if not data:
        return HttpResponseBadRequest()

    data = json.loads(data)
    new_items = []
    for item in data:
        stamp = item.pop('timestamp')
        category = item.pop('category', None)
        available_fields = set(field.name for field in Bounced._meta.get_fields()) - {'id'}
        item = {k: v for k, v in list(item.items()) if k in available_fields}  # remove other fields

        bounced = Bounced(**item)
        bounced.eventDateTime = datetime.fromtimestamp(stamp)
        if category:
            bounced.category = str(category)
        new_items.append(bounced)
    if new_items:
        Bounced.objects.bulk_create(new_items)
    return HttpResponse()
