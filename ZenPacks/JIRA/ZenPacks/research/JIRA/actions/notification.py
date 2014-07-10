
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
        serviceRoot = notification.content['service_group_root']

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

        issueValues = {
            'summary' : summary,
            'description' : description,
            'eventraw' : eventRawData,
            'customfields' : customfields
        }

        log.debug('[research] base issue values : %s' % (issueValues))

        targetValues = {
            'project' : issueProject,
            'issuetype' : issueType,
            'priority' : issuePriority,
            'serviceroot' : serviceRoot 
        }

        log.debug('[research] base target values : %s' % (targetValues))

        self.connectJIRA(jiraURL, jiraUser, jiraPass)

        if (signal.clear):
            log.debug('[research] event cleared')
            self.clearEventIssue(environ, targetValues, issueValues)
        else:
            self.createEventIssue(environ, targetValues, issueValues)

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

    def setIssueValues(self, data, targetValues, issueValues):
        log.debug('[research] process issue values')

        if ('project' in targetValues):
            issueValues['project'] = {
                'key' : targetValues['project']
            }
        if ('issuetype' in targetValues):
            issueValues['issuetype'] = {
                'name' : targetValues['issuetype']
            }

        issueValues['summary'] = self.processEventFields(
            data, issueValues['summary'], 'Summary'
        )
        issueValues['description'] = self.processEventFields(
            data, issueValues['description'], 'Description'
        )

        log.debug('[research] issue values : %s' % (issueValues))

        return issueValues

    def setCustomFieldValues(self, data, targetValues, issueValues):
        log.debug('[research] process customfield values')

        customfields = None
        if ('customfields' in issueValues):
            customfields = issueValues['customfields']
            del issueValues['customfields']

        if (customfields):
            customfields = json.loads(customfields)
        else:
            customfields = {}

        if ('priority' in targetValues):
            customfields['Priority'] = targetValues['priority']

        if ('serviceroot' in targetValues):
            customfields['Service'] = targetValues['serviceroot'] 

        if ('eventraw' in issueValues):
            customfields['Zenoss EventRAW'] = self.processEventFields(
                data, issueValues['eventraw'], 'Event Raw Data'
            )
            del issueValues['eventraw']

        customfields = self.setZenossFields(data, customfields)

        log.debug('[research] customfield values : %s' % (customfields))

        createmeta = self.jira.createmeta(
            projectKeys = targetValues['project'],
            issuetypeNames = targetValues['issuetype'],
            expand = 'projects.issuetypes.fields'
        )

        issuetype = None
        fields = None
        if (createmeta):
            if ('projects' in createmeta):
                if ('issuetypes' in createmeta['projects'][0]):
                    issuetype = createmeta['projects'][0]['issuetypes'][0]
                    log.debug('[research] createmeta issuetype : available')
            if (issuetype):
                if ('fields' in issuetype):
                    fields = issuetype['fields']
                    log.debug('[research] createmeta fields : available')
        else:
            log.debug('[research] createmeta : NOT AVAILABLE')

        if (fields):
            for fKey, fAttr in fields.iteritems():
                if ('name' in fAttr):
                    if (fAttr['name'] in customfields):
                        log.debug('[research] customfield found')
                        fieldValue = customfields[fAttr['name']]
                        if ('allowedValues' in fAttr):
                            log.debug('[research] has customfield options')
                            fieldValue = self.getCustomFieldOption(
                                fAttr['allowedValues'], fieldValue
                            )
                        if (fieldValue):
                            log.debug('[research] cf (%s) set to %s' % (
                                fAttr['name'], fieldValue)
                            )
                            issueValues[fKey] = fieldValue

        log.debug('[research] issue customfields : %s' % (issueValues))

        return issueValues

    def setZenossFields(self, data, customfields):
        log.debug('[research] process customfield values')

        if (not customfields):
            customfields = {}

        zEventID = self.getEventID(data)
        if (zEventID):
            customfields['Zenoss ID'] = zEventID

        zDeviceID = self.getDeviceID(data)
        if (zDeviceID):
            customfields['Zenoss DevID'] = zDeviceID

        zBaseURL = self.getBaseURL(data) 
        if (zBaseURL):
            customfields['Zenoss Instance'] = zBaseURL

        zEnv = self.getEnvironment(data)
        if (zEnv):
            customfields['Environment'] = zEnv 

        if ('Service' in customfields):
            zSrvc = self.getServiceGroup(data, customfields['Service'])
            if (zSrvc):
                customfields['Service'] = zSrvc

        zLoc = self.getLocation(data)
        if (zLoc):
            customfields['DataCenter'] = zLoc

        log.debug('[research] Zenoss customfields : %s' % (customfields))

        return customfields 

    def createEventIssue(self, data, targetValues, issueValues):
        log.debug('[research] create event issue')

        issueValues = self.setIssueValues(
            data, targetValues, issueValues
        )

        issueValues = self.setCustomFieldValues(
            data, targetValues, issueValues
        )

        project = targetValues['project']

        eventID = self.getEventID(data)
        baseHost = self.getBaseHost(data) 
        deviceID = self.getDeviceID(data)

        hasIssues = self.hasEventIssues(project, baseHost, eventID)

        if (hasIssues):
            log.info('[research] issue exists for EventID %s' % (eventID))
        else:
            newissue = self.jira.create_issue(fields = issueValues)
            log.info('[research] issue created : %s' % (newissue.key))

    def clearEventIssue(self, data, targetValues, issueValues):
        log.debug('[research] clear event issue')

        project = targetValues['project']

        eventID = self.getEventID(data)
        baseHost = self.getBaseHost(data) 

        issues = self.getEventIssues(project, baseHost, eventID)

        issueValues = self.setIssueValues(
            data, targetValues, issueValues
        )

        description = issueValues['description']

        for issue in issues:
            zenossCLR = self.getCustomFieldID(issue, 'Zenoss EventCLR')
            if (zenossCLR):
                issue.update(fields = {zenossCLR : eventCLR})
                log.debug('[research] EventCLR updated')
            if (description):
                self.jira.add_comment(issue.key, description)
                log.debug('[research] EventCLR commented')

    def hasEventIssues(self, project, eventINS, eventID):
        log.debug('[research] has event issues')

        issues = self.getEventIssues(project, eventINS, eventID)

        log.debug('[research] has event issues : %s' % (len(issues) > 0))

        return (len(issues) > 0)

    def getEventIssues(self, project, eventINS, eventID):
        log.debug('[research] get event issues')

        issues = []

        if (eventID):
            issueFilter = '(project = "%s")'
            issueFilter += ' and ("Zenoss Instance" ~ "%s")'
            issueFilter += ' and ("Zenoss ID" ~ "%s")'
            issueFilter = issueFilter % (project, eventINS, eventID)
            log.debug('[research] event issue filter : %s' % (issueFilter))

            try:
                issues = self.jira.search_issues(issueFilter)
                log.debug('[research] event issues : %s' % (len(issues)))
            except JIRAError as jx:
                log.error('[research] jira.error : %s' % (jx))
            except Exception as ex:
                log.error('[research] exception : %s' % (ex))

        return issues

    def getCustomFieldOption(
        self, fieldOptions, value, defaultValue = '',  exactMatch = False):
        log.debug('[research] get customfield options')

        if (not value):
            return None

        if (not fieldOptions):
            return None 

        bMatch = False
        bDefault = False
        matchValue = None

        for av in fieldOptions:
            if ('value' in av):
                valueName = av['value']
            elif ('name' in av):
                valueName = av['name']
            else:
                continue

            if (value.__class__.__name__ in ('str', 'unicode')):
                if (exactMatch):
                    if (valueName == value):
                        bMatch = True
                else:
                    if (re.match(value, valueName, re.IGNORECASE)):
                        bMatch = True

            if (bMatch):
                if ('id' in av):
                    return {'id' : av['id']}
                else:
                    return valueName

        return None

    def getIssueCustomFieldID(self, issue, fieldName):
        log.debug('[research] get issue customfield ID')

        fieldID = ''

        for field in issue.fields:
            if (field['name'].lower() == fieldName.lower()):
                log.debug('[research] customfield matched %s' % (fieldName))
                fieldID = field['id']
                break
        
        return fieldID

    def getEventID(self, data):
        log.debug('[research] get eventID')

        eventID = '${evt/evid}'
        try:
            eventID = self.processEventFields(data, eventID, 'eventID')
        except Exception:
            eventID = ''

        return eventID 

    def getDeviceID(self, data):
        log.debug('[research] get deviceID')

        deviceID = '${evt/device}'
        try:
            deviceID = self.processEventFields(data, deviceID, 'deviceID')
        except Exception:
            deviceID = ''

        return deviceID 

    def getBaseURL(self, data):
        log.debug('[research] get baseURL')

        baseURL = '${urls/baseUrl}'
        try:
            baseURL = self.processEventFields(data, baseURL, 'baseURL')
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

    def getEnvironment(self, data):
        log.debug('[research] get environment')

        eventENV = '${dev/getProductionStateString}'
        try:
            eventENV = self.processEventFields(
                data, eventENV, 'Event ENV (dev)'
            )
        except Exception:
            eventENV = '${evt/prodState}'
            try:
                eventENV = self.processEventFields(
                    data, eventENV, 'Event ENV (evt)'
                )
            except Exception:
                eventENV = ''

        return eventENV

    def getServiceGroup(self, data, valuePattern):
        log.debug('[research] get service group')

        srvcGRP = '${evt/DeviceGroups}'
        try:
            srvcGRP = self.processEventFields(data, srvcGRP, 'Service')
            srvcGRP = srvcGRP.split('|')
        except Exception:
            srvcGRP = []

        for ix in range(len(srvcGRP)):
            svcm = re.match(valuePattern, srvcGRP[ix], re.IGNORECASE)
            if (svcm):
                srvcGRP[ix] = '\(' + svcm.group(2) + '\)'
            else:
                srvcGRP[ix] = ''

        srvcGRP.append('uncategorized')

        srvcGRP = self.removeEmptyListElements(srvcGRP)

        srvcGRP = '.*(' + '|'.join(srvcGRP) + ').*'

        log.debug('[research] service group pattern : %s' % (srvcGRP))

        return srvcGRP

    def getLocation(self, data):
        log.debug('[research] get location')

        loc = '${evt/Location}'
        try:
            loc = self.processEventFields(data, loc, 'Location')
        except Exception:
            loc = ''

        return loc

    def getSiteURI(self, source):
        outURI = re.findall("((http|https)://[a-zA-Z0-9-\.:]*)", source)
        if (outURI.__class__.__name__ in ['list']):
            log.debug('[site.uri] -> %s' % (outURI)) 
            if (len(outURI) > 0):
                if (len(outURI[0]) > 0):
                    outURI = outURI[0][0]
        outURI = urlparse(source)
        return "%s://%s" % (outURI.scheme, outURI.netloc)

    def processEventFields(self, data, content, name):
        log.debug('[research] process TAL expressions')

        try:
            content = processTalSource(content, **data)
            log.debug('[research] %s : %s' % (name, content))
        except Exception:
            log.debug('[research] unable to process : %s' % (name))
            raise ActionExecutionException(
                '[research] failed to process TAL in %s' % (name))

        if (content == 'None'):
            content = ''

        return content

    def removeEmptyListElements(self, listObj):
        log.debug('[research] remove empty list elements')

        bDirty = True
        for lx in range(len(listObj)): 
            try:
                ix = listObj.index('')
                listObj[ix:ix + 1] = []
            except Exception:
                bDirty = False

            try:
                ix = listObj.index()
                listObj[ix:ix + 1] = []
                if (not bDirty):
                    bDirty = True
            except Exception:
                if (not bDirty):
                    bDirty = False

            if (not bDirty):
                break

        return listObj

    def processServiceGroupUsingRoot(self, serviceGroups, rootPattern):
        log.debug('[research] filter service group values')

        return serviceGroups

