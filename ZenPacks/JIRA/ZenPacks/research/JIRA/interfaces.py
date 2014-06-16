
import Globals

from zope.schema.vocabulary import SimpleVocabulary

from Products.Zuul.interfaces import IInfo
from Products.Zuul.form import schema
from Products.Zuul.utils import ZuulMessageFactory as _t

class IJIRAActionContentInfo(IInfo):

    jira_instance = schema.TextLine(
        title = _t(u'JIRA Target Instance'),
        description = _t(u'Base URL for JIRA instance to report issues'),
    )

    jira_user = schema.TextLine(
        title = _t(u'JIRA UserID'),
        description = _t(u'Set JIRA reporter UserID'),
    )

    jira_password = schema.Password(
        title = _t(u'JIRA Password'),
        description = _t(u'Set JIRA reporter password'),
    )

    issue_project = schema.TextLine(
        title = _t(u'JIRA Project'),
        description = _t(u'Set Issue Project'),
    )

    issue_type = schema.TextLine(
        title = _t(u'IssueType'),
        description = _t(u'Set IssueType'),
    )

    issue_priority_key = schema.TextLine(
        title = _t(u'Issue Priority'),
        description = _t(u'Set issue priority (use Priority Key)'),
    )

    issue_summary = schema.TextLine(
        title = _t(u'Issue Summary'),
        description = _t(u'Set issue summary content'),
    )

    issue_description = schema.Text(
        title = _t(u'Issue Description'),
        description = _t(u'Set issue description content'),
    )

    clear_issue_description = schema.Text(
        title = _t(u'Descripton on CLEAR'),
        description = _t(u'Set issue comment content when event cleared'),
    )

    customfield_keypairs = schema.Text(
        title = _t(u'CustomField KeyPairs'),
        description = _t(u'Define customfield keypair values (Format [json] : {"key1":"value1", ...})'),
    )

    event_rawdata = schema.Text(
        title = _t(u'Event Raw Data'),
        description = _t(u'Define event raw data (Format [json] : {"key1":"value1", ...}) default: will use raw EventObject'),
    )

