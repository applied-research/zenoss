
import Globals

from zope.interface import implements

from Products.Zuul.infos import InfoBase
from Products.Zuul.infos.actions import ActionFieldProperty
from zope.schema.fieldproperty import FieldProperty

from ZenPacks.research.JIRA.interfaces import IJIRAActionContentInfo

class JIRAActionContentInfo(InfoBase):
    implements(IJIRAActionContentInfo)

    jira_instance = ActionFieldProperty(IJIRAActionContentInfo, 'jira_instance')
    jira_user = ActionFieldProperty(IJIRAActionContentInfo, 'jira_user')
    jira_password = ActionFieldProperty(IJIRAActionContentInfo, 'jira_password')

    issue_project = ActionFieldProperty(IJIRAActionContentInfo, 'issue_project')
    issue_type = ActionFieldProperty(IJIRAActionContentInfo, 'issue_type')
    issue_priority_key = ActionFieldProperty(IJIRAActionContentInfo, 'issue_priority_key')

    issue_summary = ActionFieldProperty(IJIRAActionContentInfo, 'issue_summary')
    issue_description = ActionFieldProperty(IJIRAActionContentInfo, 'issue_description')
    clear_issue_description = ActionFieldProperty(IJIRAActionContentInfo, 'clear_issue_description')

    customfield_keypairs= ActionFieldProperty(IJIRAActionContentInfo, 'customfield_keypairs')
    event_rawdata = ActionFieldProperty(IJIRAActionContentInfo, 'event_rawdata')

    service_group_root = ActionFieldProperty(IJIRAActionContentInfo, 'service_group_root')

