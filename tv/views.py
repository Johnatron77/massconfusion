import environ
from django.db import IntegrityError

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view

from tv.helpers import transform_signal_data
from us.task_helpers import handle_timeframe_signal
from us.serializers import TimeframeKlineSignalSerializer

env = environ.Env()
environ.Env.read_env()

TV_ALERT_HOOK_PF = env('TV_ALERT_HOOK_PF')
TV_ALERT_HOOK_ENABLED = env('TV_ALERT_HOOK_ENABLED')


@api_view(['POST'])
def signal_alert_hook(request):
    if request.method == 'POST':
        pf = request.data.get('pf')
        if TV_ALERT_HOOK_ENABLED == 'true' \
                and pf is not None \
                and pf == TV_ALERT_HOOK_PF:
            del request.data['pf']
            data = transform_signal_data(request.data)
            serializer = TimeframeKlineSignalSerializer(data=data)
            if serializer.is_valid():
                try:
                    tfks = serializer.save()
                    handle_timeframe_signal(tfks)
                except IntegrityError as e:
                    print(f'Signal already exists: {e}')
                except Exception as e:
                    print(f'Error: {e}')
            else:
                print('Signal invalid')
                print(serializer.errors)

        return Response(status=status.HTTP_200_OK)
