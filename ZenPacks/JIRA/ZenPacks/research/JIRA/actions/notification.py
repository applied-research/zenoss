
import logging
log = logging.getLogger("zen.zenactiond.research.JIRA")

import Globals

from zope.interface import implements

from Products.ZenModel.UserSettings import GroupSettings
from Products.ZenUtils.guid.guid import GUIDManager

from Products.ZenModel.interfaces import IAction
from Products.ZenModel.actions import IActionBase, TargetableAction, \
    ActionExecutionException, _signalToContextDict, processTalSource 

from ZenPacks.research.JIRA.interfaces import IJIRAActionContentInfo

class JIRAReporter(IActionBase, TargetableAction):
    implements(IAction)

    id = 'JIRAReporter'
    name = 'JIRA Issue Reporter'
    actionContentInfo = IJIRAActionContentInfo 

    shouldExecuteInBatch = False

    def __init__(self):
        log.debug('[research] %s : initialized' % (self.id))
        super(JIRAReporter, self).__init__()

    def setupAction(self, dmd):
        log.debug('[research] setup : %s' % (self.name))
        self.guidManager = GUIDManager(dmd)
        self.dmd = dmd

    def executeOnTarget(self, notification, signal, target):
        self.setupAction(notification.dmd)

        log.debug('[research] execute : %s on %s' % (self.name, target))

        jiraURL = notification.content['jira_instance']
        issueProject = notification.content['issue_project']
        issueType = notification.content['issue_type']
        issuePriority = notification.content['issue_priority_key']
        customfields = notification.content['customfield_keypairs']
        eventRawData = notification.content['event_rawdata']

        summary = ''
        description = ''

        if signal.clear:
            log.info('[research] event cleared : %s' % (target))
            description = notification.content['clear_issue_description']
        else:
            log.warn('[research] event detected : %s' % (target))
            summary = notification.content['issue_summary']
            description = notification.content['issue_description']

        actor = signal.event.occurrence[0].actor
        device = None
        if actor.element_uuid:
            device = self.guidManager.getObject(actor.element_uuid)

        component = None
        if actor.element_sub_uuid:
            component = self.guidManager.getObject(actor.element_sub_uuid)

        environ = {
            'dev': device, 'component': component, 'dmd': notification.dmd
        }

        data = _signalToContextDict(
            signal, self.options.get('zopeurl'),
            notification, self.guidManager
        )

        environ.update(data)

        if environ.get('evt', None):
            environ['evt'] = self._escapeEvent(environ['evt'])

        if environ.get('clearEvt', None):
            environ['clearEvt'] = self._escapeEvent(environ['clearEvt'])

        environ['user'] = getattr(self.dmd.ZenUsers, target, None)

        try:
            summary = processTalSource(summary, **environ)
            log.debug('[research] summary : %s' % (summary))
        except Exception:
            raise ActionExecutionException(
                '[tales] failed to process Summary')

        try:
            description = processTalSource(description, **environ)
            log.debug('[research] description : %s' % (description))
        except Exception:
            raise ActionExecutionException(
                '[tales] failed to process Description')

        try:
            customfields = processTalSource(customfields, **environ)
            log.debug('[research] customfields : %s' % (customfields))
        except Exception:
            raise ActionExecutionException(
                '[tales] failed to process CustomField KeyPairs')

        try:
            eventRawData = processTalSource(eventRawData, **environ)
            log.debug('[research] event raw data : %s' % (eventRawData))
        except Exception:
            raise ActionExecutionException(
                '[tales] failed to process Event Raw Data')

        log.info("[research] event update reported : %s" % (jiraURL));

    def getActionableTargets(self, target):
        ids = [target.id]
        if isinstance(target, GroupSettings):
            ids = [x.id for x in target.getMemberUserSettings()]
        return ids

    def _escapeEvent(self, evt):
        """
        Escapes the relavent fields of an event context for event commands.
        """
        if evt.message:
            evt.message = self._wrapInQuotes(evt.message)
        if evt.summary:
            evt.summary = self._wrapInQuotes(evt.summary)
        return evt

    def _wrapInQuotes(self, msg):
        """
        Wraps the message in quotes, escaping any existing quote.

        Before:  How do you pronounce "Zenoss"?
        After:  "How do you pronounce \"Zenoss\"?"
        """
        QUOTE = '"'
        BACKSLASH = '\\'
        return ''.join((QUOTE, msg.replace(QUOTE, BACKSLASH + QUOTE), QUOTE))

    def updateContent(self, content=None, data=None):
        super(JIRAReporter, self).updateContent(content, data)

        updates = dict()
        properties = [
            'jira_instance', 'jira_user', 'jira_password',
            'issue_project', 'issue_type', 'issue_priority_key',
            'issue_summary', 'issue_description', 'clear_issue_summary',
            'customfield_keypairs', 'event_rawdata'
        ]

        for k in properties:
            updates[k] = data.get(k)

        content.update(updates)

