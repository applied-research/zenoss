
import logging
log = logging.getLogger("zen.useraction.actions")

import Globals

from zope.interface import implements

from Products.ZenModel.interfaces import IAction
from Products.ZenModel.actions import IActionBase, TargetableAction, \
    processTalSource, ActionExecutionException

from ZenPacks.research.JIRA.interfaces import IJIRAActionContentInfo

class JIRAReporter(IActionBase, TargetableAction):
    implements(IAction)

    id = 'JIRAReporter'
    name = 'JIRA Issue Reporter'
    actionContentInfo = IJIRAActionContentInfo 

    shouldExecuteInBatch = False

    def __init__(self):
        super(JIRAReporter, self).__init__()

    def setupAction(self, dmd):
        self.guidManager = GUIDManager(dmd)
        self.dmd = dmd

    def executeOnTarget(self, notification, signal, target):
        self.setupAction(notification.dmd)

        log.debug('Executing action: %s on %s', self.name, target)

        if signal.clear:
            description = notification.content['clear_issue_description']
        else:
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
            command = processTalSource(command, **environ)
        except Exception:
            raise ActionExecutionException(
                'Unable to perform TALES evaluation on "%s"' % command)

        log.info("Event Reported to JIRA Instance");

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
            'jira_instance', 'issuetype', 'priority_key',
            'issue_summary', 'issue_description',
            'clear_issue_summary', 'customfield_keypairs'
        ]

        for k in properties:
            updates[k] = data.get(k)

        content.update(updates)

