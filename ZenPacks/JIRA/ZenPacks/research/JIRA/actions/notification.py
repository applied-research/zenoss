
import logging
log = logging.getLogger("zen.zenactiond.research.JIRA")

import re

import Globals

from zope.interface import implements

from Products.ZenModel.UserSettings import GroupSettings
from Products.ZenUtils.guid.guid import GUIDManager

from Products.ZenModel.interfaces import IAction
from Products.ZenModel.actions import IActionBase, TargetableAction, \
    ActionExecutionException, _signalToContextDict, processTalSource 

from ZenPacks.research.JIRA.interfaces import IJIRAActionContentInfo

# import jira client
from jira.client import JIRA
from jira.exceptions import JIRAError

# import urlparse
from urlparse import urlparse

# import json
import json

class JIRAReporter(IActionBase, TargetableAction):
    implements(IAction)

    id = 'JIRAReporter'
    name = 'JIRA Issue Reporter'
    actionContentInfo = IJIRAActionContentInfo 

    shouldExecuteInBatch = False

    def __init__(self):
        log.debug('[research] %s : initialized' % (self.id))
        super(JIRAReporter, self).__init__()

        self.connected = False
        self.jira = None

    def setupAction(self, dmd):
        log.debug('[research] setup : %s' % (self.name))
        self.guidManager = GUIDManager(dmd)
        self.dmd = dmd

    def executeOnTarget(self, notification, signal, target):
        self.setupAction(notification.dmd)

        log.debug('[research] execute : %s on %s' % (self.name, target))

        jiraURL = notification.content['jira_instance']
        jiraUser = notification.content['jira_user']
        jiraPass = notification.content['jira_password']
        
        issueProject = notification.content['issue_project']
        issueType = notification.content['issue_type']
        issuePriority = notification.content['issue_priority_key']
        customfields = notification.content['customfield_keypairs']
        eventRawData = notification.content['event_rawdata']

        summary = ''
        description = ''

        if (signal.clear):
            log.info('[research] event cleared : %s' % (target))
            description = notification.content['clear_issue_description']
        else:
            log.warn('[research] event detected : %s' % (target))
            summary = notification.content['issue_summary']
            description = notification.content['issue_description']

        actor = signal.event.occurrence[0].actor
        device = None
        if (actor.element_uuid):
            device = self.guidManager.getObject(actor.element_uuid)

        component = None
        if (actor.element_sub_uuid):
            component = self.guidManager.getObject(actor.element_sub_uuid)

        environ = {
            'dev': device, 'component': component, 'dmd': notification.dmd
        }

        data = _signalToContextDict(
            signal, self.options.get('zopeurl'),
            notification, self.guidManager
        )

        environ.update(data)

        if (environ.get('evt', None)):
            environ['evt'] = self._escapeEvent(environ['evt'])

        if (environ.get('clearEvt', None)):
            environ['clearEvt'] = self._escapeEvent(environ['clearEvt'])

        environ['user'] = getattr(self.dmd.ZenUsers, target, None)

        try:
            summary = processTalSource(summary, **environ)
            log.debug('[research] summary : %s' % (summary))
        except Exception:
            if (device):
                raise ActionExecutionException(
                    '[tales] failed to process Summary')
            else:
                try:
                    summary = '${evt/device} : ${evt/summary}'
                    summary = processTalSource(summary, **environ)
                    log.debug('[research] summary (evt) : %s' % (summary))
                except Exception:
                    raise ActionExecutionException(
                        '[tales] failed to process Summary (evt)')

        try:
            description = processTalSource(description, **environ)
            log.debug('[research] description : %s' % (description))
        except Exception:
            if (device):
                raise ActionExecutionException(
                    '[tales] failed to process Description')
            else:
                try:
                    description = '${evt/device} : ${evt/summary}'
                    description = processTalSource(description, **environ)
                    log.debug('[research] description : %s' % (description))
                except Exception:
                    raise ActionExecutionException(
                        '[tales] failed to process Description (evt)')

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

        self.connectJIRA(jiraURL, jiraUser, jiraPass)

        baseHost = self.getBaseHost(environ) 
        eventID = self.getEventID(environ)
        deviceID = self.getDeviceID(environ)

        issues = self.getEventIssues(issueProject, baseHost, eventID)
        hasIssues = self.hasEventIssues(issueProject, baseHost, eventID)

        if (signal.clear):
            self.clearEventIssue(notification, environ)
        else:
            self.createEventIssue(notification, environ) 

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
            'customfield_keypairs', 'event_rawdata', 'service_group_root'
        ]

        for k in properties:
            updates[k] = data.get(k)

        content.update(updates)

# jira client methods

    def connectJIRA(self, URL, user, password):
        log.debug('[research] : connecting to %s' % (URL))

        basicauth = (user, password)

        try:
            self.jira = JIRA(
                options = {'server' : URL},
                basic_auth = basicauth
            )
            self.connected = True
            log.debug('[research] : connected to %s' % (URL))
        except JIRAError as jx:
            log.error('[research] jira.error : %s' % (jx))
        except Exception as ex:
            log.debug('[research] exception : %s' % (ex))
        finally:
            log.debug('[research] connection info (%s)' % (URL))

    def createEventIssue(self, notification, data):
        log.debug('[research] create event issue')

    def clearEventIssue(self, notification, data):
        log.debug('[research] clear event issue')

    def hasEventIssues(self, project, eventINS, eventID):
        log.debug('[research] has event issues')

        issues = self.getEventIssues(project, eventINS, eventID)

        log.debug('[research] has event issues : %s' % (len(issues) > 0))
        
        return (len(issues) > 0)

    def getEventIssues(self, project, eventINS, eventID):
        log.debug('[research] get event issues')
        
        if (eventID):
            issueFilter = '(project = "%s")'
            issueFilter += ' and ("Zenoss Instance" ~ "%s")'
            issueFilter += ' and ("Zenoss ID" ~ "%s")'
            issueFilter = issueFilter % (project, eventINS, eventID)
            issues = self.jira.search_issues(issueFilter)
            log.debug('[research] event issue filter : %s' % (issueFilter))
        else:
            issues = []

        log.debug('[research] event issues : %s' % (len(issues)))

        return issues

    def getEventID(self, data):
        log.debug('[research] get eventID')

        eventID = '${evt/evid}'
        try:
            eventID = processTalSource(eventID, **data)
            log.debug('[research] eventID : %s' % (eventID))
        except Exception:
            log.debug('[research] eventID : NOT AVAILABLE')
            eventID = ''

        return eventID 

    def getDeviceID(self, data):
        log.debug('[research] get deviceID')

        deviceID = '${evt/device}'
        try:
            deviceID = processTalSource(deviceID, **data)
            log.debug('[research] deviceID : %s' % (deviceID))
        except Exception:
            log.debug('[research] deviceID : NOT AVAILABLE')
            deviceID = ''

        return deviceID 

    def processEventFields(self, content, data, name):

        try:
            content = processTalSource(content, **data)
            log.debug('[research] %s : %s' % (name, content))
        except Exception:
            raise ActionExecutionException(
                '[tales] failed to process %' % (name))

        return content

    def processCustomFields(self):
        pass

    def getBaseURL(self, data):
        log.debug('[research] get baseURL')

        baseURL = '${urls/baseUrl}'
        try:
            baseURL = processTalSource(baseURL, **data)
            log.debug('[research] baseURL : %s' % (baseURL))
        except Exception:
            baseURL = ''

        if (baseURL):
            baseURL = self.getSiteURI(baseURL)

        return baseURL
        
    def getBaseHost(self, data):
        log.debug('[research] get baseHost')

        baseHost = ''

        baseHost = self.getBaseURL(data)

        return urlparse(baseHost).hostname

    def getSiteURI(self, source):
        outURI = re.findall("((http|https)://[a-zA-Z0-9-\.:]*)", source)
        if (outURI.__class__.__name__ in ['list']):
            log.debug('[site.uri] -> %s' % (outURI)) 
            if (len(outURI) > 0):
                if (len(outURI[0]) > 0):
                    outURI = outURI[0][0]
        outURI = urlparse(source)
        return "%s://%s" % (outURI.scheme, outURI.netloc)

