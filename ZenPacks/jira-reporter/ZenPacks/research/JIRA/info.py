
import Globals

from zope.interface import implements

from Products.Zuul.infos import InfoBase
from Products.Zuul.infos.actions import ActionFieldProperty
from zope.schema.fieldproperty import FieldProperty

from ZenPacks.research.JIRA.interfaces import IJIRAActionContentInfo

_marker = object()

class JIRAActionContentInfo(InfoBase):
    implements(IJIRAActionContentInfo)
    jira_instance = ActionFieldProperty(IJIRAActionContentInfo, 'jira_instance')
    issue_summary = ActionFieldProperty(IJIRAActionContentInfo, 'issue_summary')
    issue_description = ActionFieldProperty(IJIRAActionContentInfo, 'issue_description')
    clear_issue_summary = ActionFieldProperty(IJIRAActionContentInfo, 'clear_issue_summary')

