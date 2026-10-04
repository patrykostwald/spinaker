from rest_framework import serializers
from rest_framework.exceptions import Throttled
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from news.account_security import AccountEnabled
from news.accounts import OpinionReadThrottle
from news import interview_votes as votes


class InterviewAddThrottle(UserRateThrottle):
    scope = 'interview_add'
    rate = '10/hour'


class InterviewVoteThrottle(UserRateThrottle):
    scope = 'interview_vote'
    rate = '30/minute'


class BallotInput(serializers.Serializer):
    day = serializers.DateField(required=False)


class AddInput(BallotInput):
    url = serializers.CharField(max_length=500)


class MessageInput(BallotInput):
    text = serializers.CharField(max_length=500)


class VoteInput(BallotInput):
    candidate_id = serializers.IntegerField(min_value=1)


class InterviewBallotView(APIView):
    def throttled(self, request, wait):
        raise Throttled(wait=wait, detail='Zbyt wiele zapytań. Spróbuj ponownie za chwilę.')

    def get_permissions(self):
        return [] if self.request.method == 'GET' else [AccountEnabled(), IsAuthenticated()]

    def get_throttles(self):
        if self.request.method == 'GET':
            return [OpinionReadThrottle()]
        return [InterviewVoteThrottle() if isinstance(self, InterviewVoteView) else InterviewAddThrottle()]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response

    def get(self, request):
        data = BallotInput(data=request.query_params)
        data.is_valid(raise_exception=True)
        return Response(votes.ballot_data(data.validated_data.get('day', votes.yesterday()), request.user))

    def post(self, request):
        data = AddInput(data=request.data)
        data.is_valid(raise_exception=True)
        day = data.validated_data.get('day', votes.yesterday())
        candidate = votes.add_candidate(request.user, day, data.validated_data['url'])
        return Response(votes.ballot_data(day, request.user) | {'added': candidate.pk})


class InterviewVoteView(InterviewBallotView):
    http_method_names = ['post', 'options']

    def post(self, request):
        data = VoteInput(data=request.data)
        data.is_valid(raise_exception=True)
        day = data.validated_data.get('day', votes.yesterday())
        votes.cast_vote(request.user, day, data.validated_data['candidate_id'])
        return Response(votes.ballot_data(day, request.user))


class InterviewMessageView(InterviewBallotView):
    http_method_names = ['post', 'options']

    def post(self, request):
        data = MessageInput(data=request.data)
        data.is_valid(raise_exception=True)
        day = data.validated_data.get('day', votes.yesterday())
        votes.send_message(request.user, day, data.validated_data['text'])
        return Response(votes.ballot_data(day, request.user) | {'sent': True})
