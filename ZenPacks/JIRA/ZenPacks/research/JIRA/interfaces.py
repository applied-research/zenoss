
import Globals

from zope.schema.vocabulary import SimpleVocabulary

from Products.Zuul.interfaces import IInfo
from Products.Zuul.form import schema
from Products.Zuul.utils import ZuulMessageFactory as _t

from zope.schema.vocabulary import SimpleVocabulary

import textwrap

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
        default = u'Incident',
    )

    issue_priority_key = schema.TextLine(
        title = _t(u'Issue Priority'),
        description = _t(u'Set issue priority (use Priority Key)'),
    )

    issue_summary = schema.TextLine(
        title = _t(u'Issue Summary'),
        description = _t(u'Set issue summary content'),
        default = u'Device : ${evt/device} (${evt/ipAddress}) | ${evt/summary}',
    )

    issue_description = schema.Text(
        title = _t(u'Issue Description'),
        description = _t(u'Set issue description content'),
        default = textwrap.dedent(text = u'''
        _master_ :  *Zenoss Instance*
        _notification_ :  *${notification/name}*
        _trigger_ :  *${trigger/name}*

        *[ device information ]*

        {quote}
        _environment_ :  *${dev/getProductionStateString}*
        _device_ :  *${evt/device}*
        _ipaddress_ :  *${evt/ipAddress}*
        {quote}

        {quote}
        _priority_ :  *${dev/getPriorityString}*
        _icmp_ :  *${dev/getPingStatusString}*
        {quote}

        {quote}
        _groups_ :  *${evt/DeviceGroups}*
        _systems_ :  *${evt/Systems}*
        _location_ :  *${evt/Location}*
        {quote}

        *[ event information ]*

        {quote}
        _component_ :  *${evt/component}*
        _event class_ :  *${evt/eventClass}*
        _event key_ : *${evt/eventKey}*
        _message_ :  *${evt/message}*
        {quote}

        {quote}
        _severity_ : *${evt/severity}*
        _count_ : ${evt/count}
        _detected_ :  *${evt/firstTime}*
        _last_ : *${evt/lastTime}*
        {quote}

        {quote}
        _agent_ :  *${evt/agent}*
        _monitor_ :  *${evt/monitor}*
        {quote}

        _reference links_ :  [ [event details | ${urls/eventUrl}] | [device details | ${urls/deviceUrl}] | [device events | ${urls/eventsUrl}] ]

        ''')
    )

    clear_issue_description = schema.Text(
        title = _t(u'Descripton on CLEAR'),
        description = _t(u'Set issue comment content when event cleared'),
        default = textwrap.dedent(text = u'''
        [ *event-cleared* ]

        _notification_ :  *${notification/name}*
        _trigger_ :  *${trigger/name}*

        {quote}
        _cleared by_ :  *${evt/clearid}*
        _cleared at_ :  *${evt/stateChange}*
        {quote}

        {quote}
        _monitor_ :  *${evt/monitor}*
        _count_ :  *${evt/count}*
        _last_ :  *${evt/lastTime}*
        {quote}

        ''')
    )

    customfield_keypairs = schema.Text(
        title = _t(u'CustomField KeyPairs'),
        description = _t(u'Define customfield keypair values (Format [json] : {"key1":"value1", ...})'),
        default = u'',
    )

    event_rawdata = schema.Text(
        title = _t(u'Event Raw Data'),
        description = _t(u'Define event raw data (Format [json] : {"key1":"value1", ...}) default: will use raw EventObject'),
    )

    service_group_root = schema.TextLine(
        title = _t(u'Service Group Roots'),
        description = _t(u'Service Group Roots (list separated by comma)'),
        default = u'^/(dcs|commercial|consumer|coretech|is)/(.*)'
    )

