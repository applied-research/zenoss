
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

# import datetime
from datetime import datetime

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
            self.clearEventIssue(environ, targetValues, issueValues)
        else:
            self.createEventIssue(environ, targetValues, issueValues)

        log.debug("[research] event update reported : %s" % (jiraURL));

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
                            try:
                                if (fAttr['schema']['type'] in ['array']):
                                    fieldValue = [fieldValue]
                            except:
                                pass
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

        project = targetValues['project']

        eventID = self.getEventID(data)
        baseHost = self.getBaseHost(data) 
        deviceID = self.getDeviceID(data)

        hasIssues = self.hasEventIssues(project, baseHost, eventID)

        if (hasIssues):
            log.warn('[research] issue exists for EventID %s' % (eventID))
        else:
            issueValues = self.setIssueValues(
                data, targetValues, issueValues
            )
            issueValues = self.setCustomFieldValues(
                data, targetValues, issueValues
            )

            newissue = self.jira.create_issue(fields = issueValues)
            log.info('[research] issue created : %s' % (newissue.key))

    def clearEventIssue(self, data, targetValues, issueValues):
        log.debug('[research] clear event issue')

        project = targetValues['project']

        eventID = self.getEventID(data)
        baseHost = self.getBaseHost(data) 

        issues = self.getEventIssues(project, baseHost, eventID)

        if (not issues):
            log.warn('[research] no issue mapped to clear : %s' % (eventID))
            return

        issueValues = self.setIssueValues(
            data, targetValues, issueValues
        )

        description = issueValues['description']

        eventCLR = self.getEventClearDate(data)

        for issue in issues:
            zenossCLR = self.getCustomFieldID(issue, 'Zenoss EventCLR')
            issuekey = issue.key
            if (zenossCLR):
                issue.update(fields = {zenossCLR : eventCLR})
                log.info('[research] EventCLR updated : %s' % (issuekey))
            if (description):
                self.jira.add_comment(issue.key, description)
                log.info('[research] EventCLR commented : %s' % (issuekey))

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
        self, fieldOptions, value, defaultValue = '',
        exactMatch = False, firstMatch = False):
        log.debug('[research] get customfield options')

        if (not value):
            return None

        if (not fieldOptions):
            return None 

        bDefault = False
        matchValue = None

        if (value.__class__.__name__ in ('str', 'unicode')):
            value = value.split(';')
            if (len(value) > 1):
                defaultValue = value[1].strip()
                log.debug('[research] option default : %s' % (defaultValue))
            value = value[0].strip()

        if (not value):
            log.debug('[research] invalid option value : %s' % (value))

        for av in fieldOptions:
            if ('value' in av):
                valueName = av['value']
            elif ('name' in av):
                valueName = av['name']
            else:
                continue

            if (value):
                if (value.__class__.__name__ in ('str', 'unicode')):
                    if (exactMatch):
                        value = '^%s$' % (value)
                    if (re.match(value, valueName, re.IGNORECASE)):
                        if ('id' in av):
                            matchValue = {'id' : av['id']}
                        else:
                            matchValue = valueName
                        if (firstMatch):
                            break

            if (not defaultValue):
                continue

            if (defaultValue.__class__.__name__ in ('str', 'unicode')):
                if (re.match(defaultValue, valueName, re.IGNORECASE)):
                    bDefault = True
                    if ('id' in av):
                        defaultValue = {'id' : av['id']}
                    else:
                        defaultValue = valueName
                    if (not value):
                        break

        if (not matchValue):
            if (bDefault):
                log.debug('[research] default option : %s' % (defaultValue))
                matchValue = defaultValue

        return matchValue

    def getCustomFieldID(self, issue, fieldName):
        log.debug('[research] get issue customfield ID')

        fieldID = ''

        for field in self.jira.fields():
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

    def getEventClearDate(self, data):
        log.debug('[research] get event clear date')

        eventCLR = '${evt/stateChange}'
        try:
            eventCLR = self.processEventFields(data, eventCLR, 'clear date')
        except Exception:
            eventCLR = ''

        if (eventCLR):
            try:
                eventCLR = datatime.strptime(
                    eventCLR, '%Y-%m-%d %H:%M:%S'
                ).isoformat()[:19] + '.000+0000'
            except:
                try:
                    eventCLR = datatime.strptime(
                        eventCLR, '%Y-%m-%d %H:%M:%S.%f'
                    ).isoformat()[:19] + '.000+0000'
                except:
                    eventCLR = ''

        if (not eventCLR):
            eventCLR = datetime.now().isoformat()[:19] + '.000+0000'

        return eventCLR

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

        extendGRP = []
        defaultGRP = None

        valuePattern = valuePattern.split(';')
        if (len(valuePattern) > 1):
            defaultGRP = valuePattern[1].strip()
        valuePattern = valuePattern[0].strip()

        if (valuePattern):
            for ix in range(len(srvcGRP)):
                svcm = re.match(valuePattern, srvcGRP[ix], re.IGNORECASE)
                if (svcm):
                    valGRP = svcm.group(2)
                    if (valGRP):
                        valGRP = valGRP.split('/')
                        for ex in range(len(valGRP)):
                            extendGRP.append(
                                '\(' + '/'.join(valGRP[:ex + 1]) + '\)'
                            )

        log.debug('[research] service group patterns : %s' % (extendGRP))

        if (extendGRP):
            srvcGRP = '.*(' + '|'.join(extendGRP) + ').*'
        else:
            srvcGRP = ''

        if (defaultGRP):
            srvcGRP += ';' + defaultGRP

        log.debug('[research] service pattern : %s' % (srvcGRP))

        return srvcGRP

    def getLocation(self, data):
        log.debug('[research] get location')

        loc = '${evt/Location}'
        try:
            loc = self.processEventFields(data, loc, 'Location')
        except Exception:
            loc = ''

        for locx in loc.split('/'):
            if (locx):
                return locx

        return loc

    def getSiteURI(self, source):
        outURI = re.findall("((http|https)://[a-zA-Z0-9-\.:]*)", source)
        if (outURI.__class__.__name__ in ['list']):
            if (len(outURI) > 0):
                if (len(outURI[0]) > 0):
                    outURI = outURI[0][0]
        log.debug('[research] zenoss URL : %s' % (outURI)) 
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

