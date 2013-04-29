import datetime
import factory
from apps.videos.models import Video 
from apps.videos.models import VideoUrl
from apps.videos.models import SubtitleLanguage
from apps.videos.types import video_type_registrar
from apps.teams.models import Team
from apps.teams.models import TeamMember
from apps.teams.models import MembershipNarrowing
from apps.teams.models import Task
from apps.teams.models import TeamVideo
from apps.teams.models import Invite
from apps.teams.models import Application
from apps.teams.models import Project
from apps.teams.models import TeamLanguagePreference
from apps.teams.models import Workflow 
from apps.teams.models import BillingReport
from apps.auth.models import CustomUser as User
from apps.auth.models import UserLanguage
from apps.messages.models import Message
from apps.subtitles.models import SubtitleLanguage

class TeamManagerLanguageFactory(factory.Factory):
    FACTORY_FOR = MembershipNarrowing


class VideoFactory(factory.Factory):
    """Creates a video using a sequence.

    """
    FACTORY_FOR = Video
    title = factory.Sequence(lambda n: 'Test video number' + n)
    description = "Greatest Video ever made"
    created = datetime.datetime.now()

class VideoUrlFactory(factory.Factory):
    """Create a video url to use in creating a video.

    """
    FACTORY_FOR = VideoUrl
    url = factory.Sequence(lambda n: 'http://unisubs.example.com/'+ n +'.mp4')
    type = 'H'
    primary=True
    original=True
    video = factory.SubFactory(VideoFactory)
    video__title = factory.Sequence(lambda n: ('Test Video %s' % n))



class UserLangFactory(factory.Factory):
    FACTORY_FOR = UserLanguage

class UserFactory(factory.Factory):
    FACTORY_FOR = User
    username = factory.Sequence(lambda n: 'TestUser' + n)
    password = 'sha1$pQQnrW0KJTHi$0000b329a889855361001a7e3bd113efbe818f7d'
    email = 'testuser@example.com'


class TeamFactory(factory.Factory):
    FACTORY_FOR = Team
    name = factory.Sequence(lambda n: 'Test Team' + n)
    slug = factory.Sequence(lambda n: 'test-team-' + n)

class TeamMemberFactory(factory.Factory):
    FACTORY_FOR = TeamMember
    team = factory.SubFactory(TeamFactory)
    role = TeamMember.ROLE_OWNER
    user = factory.SubFactory(UserFactory)

class TeamContributorMemberFactory(factory.Factory):
    FACTORY_FOR = TeamMember
    role = TeamMember.ROLE_CONTRIBUTOR
    user = factory.SubFactory(UserFactory, username=
        factory.Sequence(lambda n: 'ContributorUser' + n))


class TeamAdminMemberFactory(factory.Factory):
    FACTORY_FOR = TeamMember
    role = TeamMember.ROLE_ADMIN
    user = factory.SubFactory(UserFactory, username=
        factory.Sequence(lambda n: 'AdminUser' + n))

class TeamOwnerMemberFactory(factory.Factory):
    FACTORY_FOR = TeamMember
    role = TeamMember.ROLE_OWNER
    user = factory.SubFactory(UserFactory, username=
        factory.Sequence(lambda n: 'OwnerUser' + n))

class TeamManagerMemberFactory(factory.Factory):
    FACTORY_FOR = TeamMember
    role = TeamMember.ROLE_MANAGER
    user = factory.SubFactory(UserFactory, username=
        factory.Sequence(lambda n: 'TeamManager' + n))


class TeamVideoFactory(factory.Factory):
    FACTORY_FOR = TeamVideo
    team = factory.SubFactory(TeamFactory)
    video = factory.SubFactory(VideoFactory)
    added_by = factory.SubFactory(UserFactory)
    created = datetime.datetime.now()

class TeamProjectFactory(factory.Factory):
    FACTORY_FOR = Project
    team = factory.SubFactory(TeamFactory)
    created = datetime.datetime.now()
    name = factory.Sequence(lambda n: 'TestProject' + n)


class TeamInviteFactory(factory.Factory):
    FACTORY_FOR = Invite


class ApplicationFactory(factory.Factory):
    FACTORY_FOR = Application
    created = datetime.datetime.now()


class TeamLangPrefFactory(factory.Factory):
    FACTORY_FOR = TeamLanguagePreference
    team = factory.SubFactory(TeamFactory)

class WorkflowFactory(factory.Factory):
    FACTORY_FOR = Workflow
    
class TaskFactory(factory.Factory):
    FACTORY_FOR = Task 
    team_video = factory.SubFactory(TeamVideoFactory)

class BillingFactory(factory.Factory):
    FACTORY_FOR = BillingReport 
    type = 2

