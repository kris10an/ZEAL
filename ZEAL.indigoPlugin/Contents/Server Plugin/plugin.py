#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################

import indigo

import os
import sys
import logging
import json, operator
#import csv,codecs,cStringIO
from lib.csvUnicode import unicodeReader, unicodeWriter, UTF8Recoder
from lib.strVarTime import prettyDate, strToTime, timeToStr, timeDiff
from collections import defaultdict
from tabulate import tabulate
#from texttable.texttable import Texttable
from operator import itemgetter

# Note the "indigo" module is automatically imported and made available inside
# our global name space by the host process.

zDefs = {
	u'0x71'						: {
		u'description'			: u'Notification command class',
		u'eventName'			: u'Received notification/alarm command',
		u'file'					: u'0x71CC.csv',
		u'byteDescription'		: {8:u'Notification report', 9:u'Alarm type', 10:u'Alarm level', 11:u'Reserved', 12:u'Notification status', 13:u'Notification type', 14:u'Event', 15:u'Event parameters length'},
		u'types'				: {}
		},
	u'0x80'						: {
		u'description'			: u'Battery command class'
		},
	u'noAck'					: {
		u'description'			: u'No ack from Z-wave device'
		},
	u'slowAck'					: {
		u'description'			: u'Slow ack from Z-wave device'
		}
	}

# Events to command class
eventCC = {
	u'x71received'				: u'0x71',
	u'x80received'				: u'0x80',
	u'zOut'						: u'zOut'
	}
	
zFolder = u'Z-Wave'

variableEnablePrefs = [u'triggeringNodeId', u'triggeringDeviceId', u'triggeringDeviceName', u'triggeringEventText']

##self.nodeStats	 nodeId<str> : [numIn, numOut, numOutNoReply, numNoAck, numSlowAckTriggers, minAckTime, maxAckTime, avgAckTime, numNotifications, numBatteryReports]
#nodeStatsKeys = ['in', 'out', 'outNR', 'noAck', 'slowAck', 'minAckTime', 'maxAckTime', 'avgAckTime', 'notification', 'batteryReport']
#nodeStatsMap = { 'in' : 0, 'out' : 1, 'outNR' : 2, 'noAck' : 3, 'slowAck' : 4, 'minAckTime' : 5, 'maxAckTime' : 6, 'avgAckTime': 7, 'notification' : 8, 'batteryReport' : 9 }
# 			headers = [u'Node', u'Device', u'In', u'Out', u'Notif.', u'Batt.', u'No Ack', u'Slow Ack', u'Ack min.', u'Ack max', u'Ack avg']
nodeStatsConf = [
	['in', u'In', 2], ['out', u'Out', 3], ['outNR', u'OutNoReply', 4], ['noAck', u'NoAcks', 7], ['slowAck', u'SlowAckTrigs.', 8],
	['minAckTime', u'AckMin.', 9], ['maxAckTime', u'AckMax', 10], ['avgAckTime', u'AckAvg', 11], 
	['notification', u'Notif.Rep.', 5], ['batteryReport', u'Batt.Rep.', 6] ]
	# Ordered same as self.nodeStats
	# [<property name>, <Header desc.>, <Header order>]
nodeStatsMap = dict()
for i, j in enumerate(nodeStatsConf):
	nodeStatsMap[j[0]] = i


#nodeStatsHeaders = {u'node' : u'Node', u'device' : u'Device', u'Cmds: In', u'Out', u'Notifications', u'Batt.reports', u'# Ack triggers: Slow', u'No Ack', u'AckTime (ms): Min', u'Max', u'Avg'}

########################################
# Tiny function to convert a list of integers (bytes in this case) to a
# hexidecimal string for pretty logging.
def convertListToHexStr(byteList):
	return ' '.join([u'%02X' % byte for byte in byteList])
	
########################################
# Tiny function to convert a list of integers (bytes in this case) to a
# hexidecimal list (string formatted) 
def convertListToHexStrList(byteList):
	return [u'0x%02X' % byte for byte in byteList]
	
########################################
# convert integer to hex string
def hexStr(integer):
	return u'0x%02X' % integer
	
########################################
# Safely get keys from dictionary
def safeGet(dct, defaultVal, *keys):
    for key in keys:
        try:
            dct = dct[key]
        except KeyError:
            return defaultVal
    return dct

########################################
# Nested defaultdict   
def treeDD():
    return defaultdict(treeDD)
    
		
########################################
# Iterate through dct and remove references to triggerID
def removeTriggerFromDict(d, triggerId):
	for k, v in d.iteritems():
		if isinstance(v, dict):
			d[k] = removeTriggerFromDict(v, triggerId)
		elif k == u'triggers':
			d[k] = [t for t in v if t != triggerId]
		else:
			raise ValueError(u'Possible error in triggerMap dictionary, v: %s' % unicode(v))
	return d

########################################
# Return pre-filled (empty) list for z-wave node stats, self.nodeStats
def emptyNodeStatList():
	# nodeId<str> : [numIn, numOut, numOutNr, numNoAck, numSlowAckTriggers, minAckTime, maxAckTime, avgAckTime, numNotifications, numBatteryReports]
	return [0]*10


# FIX, check json dumps for integer keys as that is not supported
################################################################################
class Plugin(indigo.PluginBase):

	########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

		self.errorState = False

		self.zDefs = zDefs # Definition of Z-wave commands etc.
		self.subscribedOutgoing = False # Set initial value to false, will be enabled if there are triggers
		self.triggerMap = treeDD() # Map of node -> Z-wave commands -> trigger id
		self.triggers = dict()
		self.zNodes = {} # Map of zwave nodes to indigo devices
		self.dependantPlugins = dict() # Plugins that this plugin relies on
		self.outgoingTriggers = False # Wheter or not there are triggers for outgoing triggers
			
		# Set plugin preferences
		self.setUpdatePluginPrefs()
		
		# FIX, remove once tested
		#self.totalAck = {}
		
		# get Z-wave defs, types and events from file
		self.getZwaveDefs()
		
		# map z-wave nodes to indigo devices
		self.getZwaveNodeDevMap()
		#self.logger.debug(self.zNodes)
		
		# map z-wave nodes and commands to indigo triggers
		
	########################################
	def __del__(self):
		indigo.PluginBase.__del__(self)
				
	########################################
	def startup(self):
		self.logger.debug(u"startup called")

		self.logger.debug(u'Subscribing to incoming Z-wave commands')
		indigo.zwave.subscribeToIncoming()
		
		self.outgoingTriggers = self.checkOutgoingTriggers()
		if self.outgoingTriggers:
			self.logger.debug(u'Subscribing to outgoing Z-wave commands, as there are triggers for outgoing')
			self.subscribedOutgoing = True
			indigo.zwave.subscribeToOutgoing()
		else:
			self.logger.debug(u'Not subscribing to outgoing Z-wave commands, as there are no triggers for outgoing')
		# FIX, don't know if it's possible to unsubscribe from outgoing z-wave commands if already subscribed
		
	########################################
	def shutdown(self):
		self.logger.debug(u"shutdown called")

		# moved to stopThread in runConcurrentThread, don't believe the below saved prefs at all times		
		# 		if self.keepStats:
		# 			self.logger.debug(u'Saving z-wave node statistics')
		# 			self.pluginPrefs[u'nodeStats'] = self.store(self.nodeStats)

	########################################
	def wakeUp(self):
	   indigo.PluginBase.wakeUp(self)
	   self.logger.debug("wakeUp method called")

	########################################
	def prepareToSleep(self):
	   indigo.PluginBase.prepareToSleep(self)
	   self.logger.debug("prepareToSleep method called")

	########################################
	def extDebug(self, msg):
		if self.extensiveDebug:
			self.debugLog(msg)

	#####
	# Set or update plugin preferences
	# 	running 		: True if plugin is already running and prefs are to be changed
	#
	def setUpdatePluginPrefs(self, running = False):
		self.logger.debug(u'CALL setUpdatePluginPrefs, running: %s' % unicode(running))
		
		# Set log levels
		if running: setText = u'Changing'
		else: setText = u'Setting'
		self.indigo_log_handler.setLevel(self.pluginPrefs.get(u'logLevel', u'INFO'))
		self.plugin_file_handler.setLevel(u'DEBUG')
		self.extensiveDebug = self.pluginPrefs.get(u'extensiveDebug', False)
		self.logger.info(u'%s log level to %s' % (setText, self.pluginPrefs.get(u'logLevel', u'INFO')))
		self.logger.debug(u'Extensive debug logging set to %s' % unicode(self.extensiveDebug))
		self.logger.debug(u'%s file handler log level to DEBUG' % (setText))
		# DEBUG		: All debug info
		# INFO		: Informational messages relevant to the user
		# WARNING	: More critical information to the user, warnings
		# ERROR		: Errors not critical for plugin execution
		# CRITICAL	: Errors critical for plugin execution, plugin will stop
		
		self.keepStats = self.pluginPrefs.get(u'keepStats', False)
		if self.keepStats:
			self.nodeStats = self.load(self.pluginPrefs.get(u'nodeStats', self.store(dict()))) # see def emptyNodeStatList() for description
			
			# Update older versions of nodeStats
			for l in self.nodeStats:
				# after adding outNR
				if len(l) == 9:
					l = l[0:1] + [0] + l[2:]
					
		# Check plugin dependencies
		self.checkDependantPlugins()
					
		
		
	########################################
	# If runConcurrentThread() is defined, then a new thread is automatically created
	# and runConcurrentThread() is called in that thread after startup() has been called.
	#
	# runConcurrentThread() should loop forever and only return after self.stopThread
	# becomes True. If this function returns prematurely then the plugin host process
	# will log an error and attempt to call runConcurrentThread() again after several seconds.
	def runConcurrentThread(self):
		try:
			counter = 0
			while True:
				self.logger.debug(u'runConcurrentThread')
				
				if counter > 0: # Skip on first loop
					self.getZwaveNodeDevMap()
				
					if self.keepStats:
						self.logger.debug(u'Periodically saving z-wave node statistics')
						self.pluginPrefs[u'nodeStats'] = self.store(self.nodeStats)
						
					# Check plugin dependencies
					self.checkDependantPlugins()
					
					# Checking for outgoing triggers
					self.outgoingTriggers = self.checkOutgoingTriggers()
					
				counter += 1
				self.sleep(3600)
		except self.StopThread:
			self.logger.debug(u'runConcurrentThread self.StopThread')
			if self.keepStats:
				self.logger.debug(u'Periodically saving z-wave node statistics')
				self.pluginPrefs[u'nodeStats'] = self.store(self.nodeStats)
		# 		if self.errorState:
		# 			# FIX, find some way to shutdown if there are errors
		# 			self.logger.error(u'Plugin in error state, stopping concurrent thread')
		# 			pass

	########################################
	def zwaveCommandReceived(self, cmd):
		byteList = cmd['bytes']			# List of the raw bytes just received. Integer values
		CC = hexStr(byteList[7]) 			# Command class
		
		#self.logger.debug(byteListHexStr)
		#self.logger.debug(type(endpoint))
		#self.logger.debug(type(byteList[7]))
		
		eventStr = list()
		debugStr = list()
		updateStats = ['in']
		
		if CC in self.zDefs:
			byteListStr = convertListToHexStr(byteList)
			byteListHexStr = convertListToHexStrList(byteList)
			nodeId = cmd['nodeId']			# Can be None! Integer
			endpoint = cmd['endpoint']		# Often will be None! Integer (??)
			updateVariables = False
			
			dev = safeGet(self.zNodes, False, unicode(nodeId), endpoint)
			if dev:
				devName = dev.name
				devId = dev.id
			else:
				devName = u'node id ' + unicode(nodeId)
				devId = 0
			
			# Notification report
			if CC == u'0x71' and byteList[8] == 5:
			
				updateStats.append('notification')
				
				if byteList[9] != 0: # Alarm command version 1
					self.logger.debug(u"received: %s (node %03d, endpoint %s)" % (byteListStr, nodeId, endpoint))
					self.logger.debug(u'Command class:		%s (%s)' % (CC, self.zDefs[CC][u'description']))
					self.logger.debug(u'Command:			%s' % (byteList[8]))
					self.logger.debug(u'V1 Alarm Type:		%s' % (byteList[9]))
					self.logger.debug(u'V1 Alarm Level:		%s' % (byteList[10]))
					
					eventStr.append(u'Received "%s" alarm report (v1), alarm type %d, alarm level %d' % (devName, byteList[9], byteList[10]))
					self.logger.info(eventStr[-1])
					# FIX trigger
				else: # Notification command version 2-8
					# FIX use descriptions from zDefs
					self.logger.debug(u"received: %s (node %03d, endpoint %s)" % (byteListStr, nodeId, endpoint))
					self.logger.debug(u'Command class:		%s (%s)' % (CC, self.zDefs[CC][u'description']))
					self.logger.debug(u'Command:			%s' % (byteList[8]))
					self.logger.debug(u'Notification Status: %s' % (byteList[12]))
					self.logger.debug(u'Notification Type:	%s (%s)' % (byteList[13], self.zDefs[CC][u'types'][byteListHexStr[13]][u'description']))
					self.logger.debug(u'Event:				%s (%s)' % (byteList[14], safeGet(self.zDefs, u'Unknown Event', CC, u'types', byteListHexStr[13], u'events', byteListHexStr[14], u'description')))
					
					# FIX, also include sequence number
					# FIX, notification status
					if len(byteList) >= 18:
						eventParms = u' '.join([u'{:02d}'.format(int(byteList[i])) for i in xrange(16,len(byteList)-1)])
						eventParmStr = u', event parameters ' + eventParms
						self.logger.debug(u'Event Parameters:	%s (%s)' % (eventParms, safeGet(self.zDefs, u'No description', CC, u'types', byteListHexStr[13], u'events', byteListHexStr[14], u'parameterText')))
					else:
						eventParmStr = u''

					triggered = False
					for triggerId in self.triggerMap[nodeId][CC][u'byte13'][hexStr(byteList[13])][u'byte14'][hexStr(byteList[14])].get(u'triggers', list()):
						trigger = self.triggers[triggerId]
						self.logger.debug(u'Triggering trigger id %s "%s"' % (unicode(trigger.id), unicode(trigger.name)))
						if not triggered:
							eventStr.append(u'Received "%s" notification report "%s", type %d, event %d%s' % (devName, safeGet(self.zDefs, u'Unknown Event', CC, u'types', byteListHexStr[13], u'events', byteListHexStr[14], u'description'), byteList[13], byteList[14], eventParmStr))
							self.logger.info(eventStr[-1])
						indigo.trigger.execute(trigger)
						triggered = True
						updateVariables = True
					
			# Battery report
			elif CC == u'0x80' and byteList[8] == 3: # Battery report
			
				updateStats.append('batteryReport')
			
				# FIX, move triggerId loop inside if's, to avoid having duplicated log entries in case of multiple triggers
			
				battLevel = byteList[9]
				nodeIdStr = unicode(nodeId) # Need to use string as key, json doesn't support integers
			
				self.logger.debug(u"received: %s (node %03d, endpoint %s)" % (byteListStr, nodeId, endpoint))
				self.logger.debug(u'Command class:		%s (%s)' % (CC, self.zDefs[CC][u'description']))
				self.logger.debug(u'Command:			%s' % (byteList[8]))
				self.logger.debug(u'Battery level:		%s' % (battLevel))
				
				# Low battery report				
				if battLevel == 255:
					triggerType = u'lowBattery'
					triggeredNodesKey = u'lowBatteryTriggeredNodes'
					
				# Battery level report
				else:
					triggerType = u'batteryLevel'
					triggeredNodesKey = u'batteryLevelTriggeredNodes'
					
				logged = False
				for triggerId in self.triggerMap[nodeId][CC].get(u'triggers', list()):
					
					trigger = self.triggers[triggerId]
					props = trigger.pluginProps
					
					propsUpdate = u'noUpdate'
					
					try:
						triggeredNodesDict = self.load(props.get(triggeredNodesKey, self.store(dict())))
						# Some older triggers (older plugin versions) may be of list type, change to dict. FIX, may be removed after a while
						# REMOVED, as using differetd keys, 2017-01-15
						# 						if isinstance(triggeredDeviceList, list):
						# 							self.logger.debug(u'Changed triggeredDeviceList to dictionary')
						# 							triggeredDeviceList = dict()
					except TypeError:
						triggeredNodesDict = dict()
					except:
						raise
						
					# FIX, consider adding logging based on why event did not trigger

					# trigger on low battery report
					if triggerType == u'lowBattery' and props[u'triggerLowBatteryReport']: 
						if not logged:
							eventStr.append(u'Received "%s" low battery report' % (devName))
							self.logger.warn(eventStr[-1])
							logged = True
						
						if (props[u'batteryLevelResetOn'] == u'always') or \
						 (props[u'batteryLevelResetOn'] in [u'manual', u'levelAbove'] and not nodeIdStr in triggeredNodesDict) or \
						 (props[u'batteryLevelResetOn'] == u'onTime' and 
						 timeDiff(strToTime(safeGet(triggeredNodesDict, u'1970-01-01 00:00:00', nodeIdStr)), u'now', u'seconds') >=
						 (int(props[u'batteryLevelResetTime'])*60*60)):
						
							self.logger.debug(u'Triggering trigger id %s "%s", node id %03d, device "%s"' % (unicode(trigger.id), unicode(trigger.name), nodeId, devName))
							indigo.trigger.execute(trigger)
						
							propsUpdate = u'update'
							updateVariables = True
							#propsUpdateKeys = [u'lowBattery']
						else:
							self.logger.debug(u'Low battery report, not matched trigger conditions')
						
					# Battery level report
					elif triggerType == u'batteryLevel' and props[u'triggerBatteryLevel']:
					
						# Battery level below trigger threshold
						if battLevel <= int(props[u'batteryLevel']):
							self.logger.debug(u'Received "%s" battery level below trigger threshold (%d%%), node id %03d, battery level %d%%' % (devName, int(props[u'batteryLevel']), nodeId, battLevel))
							if not logged:
								eventStr.append(u'Received "%s" battery level below trigger threshold, battery level %d%%' % (devName, battLevel))
								self.logger.warn(eventStr[-1])
								logged = True
							
							# Check if previously triggered for node, skip if previously triggered
							if (props[u'batteryLevelResetOn'] == u'always') or \
						 	 (props[u'batteryLevelResetOn'] in [u'manual', u'levelAbove'] and not nodeIdStr in triggeredNodesDict) or \
							 (props[u'batteryLevelResetOn'] == u'onTime' and
							  timeDiff(strToTime(safeGet(triggeredNodesDict, u'1970-01-01 00:00:00', nodeIdStr)), u'now', u'seconds') >=
							  (int(props[u'batteryLevelResetTime'])*60*60)):
							
								self.logger.debug(u'Triggering trigger id %s "%s", node id %03d, device "%s"' % (unicode(trigger.id), unicode(trigger.name), nodeId, devName))
								
								indigo.trigger.execute(trigger)
								self.extDebug(u'localProps: %s' % unicode(props))
								
								propsUpdate = u'update'
								updateVariables = True
								#propsUpdateKeys = [u'batteryLevel']
								
							# Battery level above reset level and configured to reset on level
							elif props[u'batteryLevelResetOn'] == u'levelAbove' and \
							 battLevel >= int(props[u'batteryLevelResetLevel']):
							 
							 	eventStr.append(u'Battery level (%d%%) above reset threshold (%d%%) for node id %s, reset trigger id %s "%s" for node' % (battLevel, int(props[u'batteryLevelResetLevel']), unicode(nodeId), unicode(trigger.id), unicode(trigger.name)))
								self.logger.info(eventStr[-1])	
							 	
							 	propsUpdate = u'reset'
							 	propsUpdateKeys = [u'lowBattery', u'batteryLevel']
							 	
							else:
								self.logger.debug(u'Battery level report, not matched trigger conditions')
							 	
							# 					
							# 					# battery level above value to reset and re-anable triggering
							# 					elif props[u'triggerBatteryLevel'] and props[u'batteryLevelResetOn'] == u'levelAbove' and byteList[9] >= int(props[u'batteryLevelResetLevel']) and (nodeId in triggeredDeviceList):
							# 						# FIX implement reset for low battery report and for onTime
							# 						# battery level above reset level, and configured to reset when battery level is above set point
							# 						#if u'triggeredDeviceList' not in props:
							# 						#	props[u'triggeredDeviceList'] = list()
							# 						
							# 						# 						tmpNodeList = list()
							# 						# 						for n in triggeredDeviceList:
							# 						# 							if n != nodeId:
							# 						# 								tmpNodeList.append(n)
							# 						tmpNodeList = [n for n in triggeredDeviceList if n != nodeId]
							# 						props[u'triggeredDeviceList'] = self.store(tmpNodeList)
							# 						self.extDebug(u'localProps: %s' % unicode(props))
							# 						trigger.replacePluginPropsOnServer(props)
							# 						
							# 						self.logger.info(u'Battery level (%d%%) above reset threshold (%d%%) for node id %s, reset trigger id %s "%s" for node' % (byteList[9], int(props[u'batteryLevelResetLevel']), unicode(nodeId), unicode(trigger.id), unicode(trigger.name)))				
						
					# Check if trigger props has been changed and are to be updated on server
					if propsUpdate == u'update':
						#self.extDebug(u'Updating last executed time for trigger, triggeredNodesDict before: %s' % (unicode(triggeredNodesDict)))
						#for pKey in propsUpdateKeys:
						# 						tmpDict = props.get(pKey + u'TriggeredNodes', dict())
						# 						tmpDict[nodeIdStr] = timeToStr()
						# 						props[pKey + u'TriggeredNodes'] = self.store(tmpDict)
						try:
							triggeredNodesDict[nodeIdStr] = timeToStr()
							props[triggeredNodesKey] = self.store(triggeredNodesDict)
							trigger.replacePluginPropsOnServer(props)
							self.logger.debug(u'Updated battery level last executed time for trigger "%s" node id %d' % (trigger.name, nodeId))
						except:
							self.logger.error(u'Could not update battery level last executed time for trigger "%s" node id %d' % (trigger.name, nodeId))
							raise
						#self.extDebug(u'Updated last executed time for trigger, triggeredDeviceList after: %s' % (unicode(triggeredNodesDict)))
					elif propsUpdate == u'reset':
						for pKey in propsUpdateKeys:
							tmpDict = props.get(pKey + u'TriggeredNodes', dict())
							if nodeIdStr in tmpDict:
								try:
									del tmpDict[nodeIdStr]
									self.logger.debug(u'Reset %s trigger for node id %d, trigger "%s"' % (pKey, nodeId, trigger.name))
								except:
									self.logger.error(u'Could not reset %s trigger for node id %d, trigger "%s"' % (pKey, nodeId, trigger.name))
									raise
							props[pKey + u'TriggeredNodes'] = self.store(tmpDict)
						trigger.replacePluginPropsOnServer(props)
			
			# Update variables, set in plugin prefs
			if updateVariables:

				self.logger.debug(u'Updating variables for triggered event')
				for varPref, varVal in zip(variableEnablePrefs, [nodeId, devId, devName, u'\n'.join(eventStr)]):
					if self.pluginPrefs.get(varPref, False):
						try:
							var = indigo.variables[int(self.pluginPrefs.get(varPref + u'Variable', 0))]
							self.extDebug(u'Updated variable "%s"' % (var.name))
						except:
							self.logger.error(u'Could not get indigo variable to store trigger information, %s' % varPref)
							continue
							
						indigo.variable.updateValue(var, value=unicode(varVal))

		self.updateNodeStats(cmd['nodeId'], *updateStats)			

	def zwaveCommandSent(self, cmd):
	
		byteList = cmd['bytes']			# List of the raw bytes just sent.
		byteListStr = convertListToHexStr(byteList)
		timeDelta = cmd['timeDelta']	# The time duration it took to receive an Z-Wave ACK for the command.
		cmdSuccess = cmd['cmdSuccess']	# True if an ACK was received (or no ACK expected), false if NAK.
		nodeId = cmd['nodeId']			# Can be None!
		endpoint = cmd['endpoint']		# Often will be None!
		updateVariables = False
		triggered = False
		debugStr = list()
		eventStr = list()
		updateStats = list()
		updateProps = dict()
		
		# get device, only if we need it later
		if not cmdSuccess or timeDelta >= 100:
			dev = safeGet(self.zNodes, False, unicode(nodeId), endpoint)
			if dev:
				devName = dev.name
				devId = dev.id
			else:
				devName = u'node id ' + unicode(nodeId)
				devId = 0

		if cmdSuccess:
			if nodeId:
				self.extDebug(u"sent: %s (node %03d ACK after %d milliseconds)" % (byteListStr, nodeId, timeDelta))
				
				# Check triggers, only if timeDelta larger than 100 to make load as small as possble
				if timeDelta >= 100:
					for triggerId in self.triggerMap[nodeId][u'zOut'].get(u'triggers', list()):
						trigger = self.triggers[triggerId]
						props = trigger.pluginProps
						if props.get(u'triggerSlowAck', False) and int(props.get(u'ackTime', 0)) <= timeDelta:
							self.logger.debug(u'Triggering trigger id %s "%s"' % (unicode(trigger.id), unicode(trigger.name)))
							if not triggered:
								eventStr.append(u'"%s" slow ACK time (%d ms) on sent z-wave command: %s' % (devName, timeDelta, byteListStr))
								self.logger.warn(eventStr[-1])
								updateStats.append('slowAck')
							indigo.trigger.execute(trigger)
							triggered = True
							updateVariables = True
				if timeDelta > 0: updateStats.append('out')
				else: updateStats.append('outNR')
				updateProps['ackTime'] = timeDelta
			else:
				self.extDebug(u"sent: %s (ACK after %d milliseconds)" % (byteListStr, timeDelta))
		else:
			self.extDebug(u"sent: %s (failed)" % (byteListStr))
			if nodeId:
				for triggerId in self.triggerMap[nodeId][u'zOut'].get(u'triggers', list()):
					trigger = self.triggers[triggerId]
					props = trigger.pluginProps
					if props.get(u'triggerNoAck', False):
						self.logger.debug(u'Triggering trigger id %s "%s"' % (unicode(trigger.id), unicode(trigger.name)))
						if not triggered:
							eventStr.append(u'"%s" no ACK on sent z-wave command: %s' % (devName, byteListStr))
							self.logger.warn(eventStr[-1])
						indigo.trigger.execute(trigger)
						triggered = True
						updateVariables = True
				updateStats.append('noAck')
						
		# Update variables, set in plugin prefs
		if updateVariables:

			self.logger.debug(u'Updating variables for triggered event')
			for varPref, varVal in zip(variableEnablePrefs, [nodeId, devId, devName, u'\n'.join(eventStr)]):
				if self.pluginPrefs.get(varPref, False):
					try:
						var = indigo.variables[int(self.pluginPrefs.get(varPref + u'Variable', 0))]
						self.extDebug(u'Updated variable "%s"' % (var.name))
					except:
						self.logger.error(u'Could not get indigo variable to store trigger information, %s' % varPref)
						continue
						
					indigo.variable.updateValue(var, value=unicode(varVal))
					
		# Update Z-wave node statistics
		if nodeId:
			self.updateNodeStats(nodeId, *updateStats, **updateProps)
		
	########################################
	# Update Z-wave node statistics
	#
	# self.nodeStats dict form:
	# nodeId<str> : [numIn, numOut, numOurNR, numNoAck, numSlowAckTriggers, minAckTime, maxAckTime, avgAckTime, numNotifications, numBatteryReports]
	#
	# *updateStat:
	# 'in', 'out', 'noAck', 'slowAck', 'notification', 'batteryReport'
	#
	# **statProps: <dict>
	# ackTime = <int>
	def updateNodeStats(self, nodeId, *updateStats, **statProps):
	
		#map = { 'in' : 0, 'out' : 1, 'noAck' : 2, 'slowAck' : 3, 'notification' : 7, 'batteryReport' : 8 }
		#map = nodeStatsMap
						
		if not self.keepStats:
			self.extDebug(u'Not updating node statistics, disabled in plugin config')
			return
			
		self.extDebug(u'Updating z-wave node statistics')
		try:
			nodeIdStr = unicode(nodeId)
		except:
			self.logger.error(u'updateNodeStats: Invalid node id specified')
			return False
			
		if nodeIdStr not in self.nodeStats:
			self.nodeStats[nodeIdStr] = emptyNodeStatList()
				
		if 'ackTime' in statProps and 'out' in updateStats:
			# min ack time
			if statProps['ackTime'] < self.nodeStats[nodeIdStr][5] or self.nodeStats[nodeIdStr][5] == 0: self.nodeStats[nodeIdStr][5] = statProps['ackTime']
			#max ack time
			if statProps['ackTime'] > self.nodeStats[nodeIdStr][6]: self.nodeStats[nodeIdStr][6] = statProps['ackTime']
			#acg ack time, possibly FIX, slightly inaccurate -> 2017-01-22: Should now be accurate as ignoring with ackTime 0. FIX when Indigo 7.0.3 is out
			self.nodeStats[nodeIdStr][7] = ((float(self.nodeStats[nodeIdStr][1]) * self.nodeStats[nodeIdStr][7]) + statProps['ackTime']) / (self.nodeStats[nodeIdStr][1] + 1)
					
			# FIX; remove once tested
			#if not nodeIdStr in self.totalAck:
			#	self.totalAck[nodeIdStr] = 0
			#self.totalAck[nodeIdStr] += statProps['ackTime']
			#self.logger.warn(u'nodeId: %s, ackTime: %d, out: %d, total ackTime: %d' % 	(nodeIdStr, statProps['ackTime'], self.nodeStats[nodeIdStr][1]+1, self.totalAck[nodeIdStr]))
		for stat in updateStats:
			#self.extDebug(u'stat prop: %s' % stat)
			if stat in nodeStatsMap:
				self.nodeStats[nodeIdStr][nodeStatsMap[stat]] += 1
			
					
				
	########################################
	def triggerStartProcessing(self, trigger):
		self.logger.debug(u'Start processing trigger "%s"' % (unicode(trigger.name)))
		
		self.getZwaveNodeTriggerMap(trigger, u'start')
		
		self.triggers[trigger.id] = trigger
		
		# FIX, consider some logic for less need for check
		self.outgoingTriggers = self.checkOutgoingTriggers()
		
		if not self.subscribedOutgoing and self.outgoingTriggers:
			self.logger.info(u'Subscribing to outgoing Z-wave commands, as there are now triggers for outgoing commands')
			self.subscribedOutgoing = True
			indigo.zwave.subscribeToOutgoing()
			
		# FIX, is there some way to unsubscribe if not needed?

	########################################
	def triggerStopProcessing(self, trigger):
		self.logger.debug(u'Stop processing trigger "%s"' % (unicode(trigger.name)))
		
		self.getZwaveNodeTriggerMap(trigger, u'stop')
		
		if trigger.id in self.triggers:
			try:
				del self.triggers[trigger.id]
			except:
				self.logger.error(u'Could not remove trigger from plugin list of triggers')
				
		self.outgoingTriggers = self.checkOutgoingTriggers()
				
		if trigger.pluginTypeId == u'zOut' and self.subscribedOutgoing and not self.outgoingTriggers:
			pass
			# Passing for now; Don't think there's a way to know if the trigger is being restarted. Will cause false info in case of trigger restart. possibly use didComm.. method.
			#self.logger.info(u'Already subscribed to outgoing Z-wave commands, as there are now no triggers for outgoing commands this could be stopped.\nAs there is no way to unsubscribe from commands, plugin could with benefit be restarted to reduce load')
			#self.subscribedOutgoing = False
			#indigo.zwave.unSubscribeOutgoing()

	#####
	# Read Z-wave commands and defs from supporting files
	#
	def getZwaveDefs(self):
		# 0x71 Notification/alarm command class
		
		try:
			x71file = os.path.join(zFolder, self.zDefs[u'0x71'][u'file'])
			self.logger.debug(u'Reading file %s' % (x71file))
			with open(x71file,'r') as fin:
				reader = unicodeReader(fin, dialect='excel', delimiter=';')
				header = next(reader)
				t=self.zDefs[u'0x71'][u'types']
				for row in reader:
					if not row[0] in t:
						t[row[0]] = {}
						t[row[0]][u'description'] = row[1]
						t[row[0]][u'version'] = row[2]
						t[row[0]][u'events'] = {}

					e = t[row[0]][u'events']
					if not row[3] in e:
						e[row[3]] = {}
						e[row[3]]['description'] = row[4]
						e[row[3]]['version'] = row[5]
						e[row[3]]['parameterText'] = row[6]
					else:
						self.logger.error(u'Duplicate notification event in file %s, misconfiguration' % (x71file))					
						
		except IOError:
			self.logger.critical(u'Could not read file %s, plugin will stop' % (x71file))
			self.errorState = True	
			raise
		except:
			self.logger.critical(u'Unexpected error while reading file %s, plugin will stop' % (x71file))
			self.errorState = True
			raise
		else:
			self.logger.debug(u"Successfully read file '%s'" % (x71file))
			#self.logger.debug(self.zDefs)
			
	#####
	# Map Z-wave nodes to devices
	#
	def getZwaveNodeDevMap(self):
	
		# FIX, may be redundant when using only triggers for received commands
		# FIX, consider making this through getZwaveNodeTriggerMap
	
		self.logger.debug(u'Mapping Z-wave nodes to indigo devices')
		# get all nodes already in zNodes, avoid to have to delete zNodes dict and temporarily risk having empty zNodes dict
		tmpNodes = set()
		for node in self.zNodes:
			tmpNodes.add(node)
		
		# add all endpoints to zNodes
		#self.logger.debug(tmpNodes)
		#nSkipped = 0
		for dev in indigo.devices.iter('indigo.zwave'):

			endpoint = dev.ownerProps.get('zwDevEndPoint') # Endpoint is Integer or None

			# 			if not dev.enabled:
			# 				self.extDebug(u'Skipping device id %s "%s" with endpoint %s - device disabled' % (unicode(dev.id), unicode(dev.name), endpoint))
			# 				nSkipped += 1
			# 				continue
			# Commented 2017-01-16: Including all devices, in order to be able to select all devices in dialogs

			if not dev.address in self.zNodes:
				self.zNodes[dev.address] = {}
				# Node id (dev.address) will be unicode type, keep it that way as that's how it's returned by Indigo
			
			#Check if this device has lower subindex, then replace previous device
			#important with = below, to update existing devices
			if not endpoint in self.zNodes[dev.address] or (dev.ownerProps.get('zwDevSubIndex') <= self.zNodes[dev.address][endpoint].ownerProps.get('zwDevSubIndex')):
				if not endpoint in self.zNodes[dev.address]: replaceStr = u'New add'
				else: replaceStr = u'Replaced: lower sub index'
				self.extDebug(u'Mapping device id %s "%s" with endpoint %s - %s' % (unicode(dev.id), unicode(dev.name), unicode(endpoint), replaceStr))
				self.zNodes[dev.address][endpoint] = dev
				tmpNodes.discard(dev.address)
			else:
				self.extDebug(u'Skipping device id %s "%s" with endpoint %s - higher subIndex' % (unicode(dev.id), unicode(dev.name), unicode(endpoint)))
			
		
		# Check if some z-wave devices might have been deleted or disabled since last update, and remove those from zNodes
		for node in tmpNodes:
			if node in self.zNodes:
				del self.zNodes[node]
				self.extDebug(u'Removed node %s from zNodes dict' % (unicode(node)))
				
		# FIX
		# Workaround, some devices send with endpoint None, while none of the Indigo devices have endpoint None (i.e. two devices
		# with endpoint 1 and 2 (example Fibaro dimmer 2)
		for node in self.zNodes:
			if 1 in self.zNodes[node] and not None in self.zNodes[node]:
				# Has endpoint 1, but not None, copy 1 to None
				self.zNodes[node][None] = self.zNodes[node][1]
				self.extDebug(u'Device id %s "%s" has no device with endpoint None - copied from 1' % (unicode(self.zNodes[node][None].id), unicode(self.zNodes[node][None].name)))
		
		#self.logger.info(u'Finished mapping %s z-wave nodes to indigo devices. Skipped %s disabled devices' % (unicode(len(self.zNodes)), unicode(nSkipped)))
		self.logger.info(u'Finished mapping %s z-wave nodes to indigo devices.' % (unicode(len(self.zNodes))))
		#self.extDebug(u'zNodes dict:\n%s' % unicode(self.zNodes))
		
	#####
	# Map Z-wave nodes to triggers
	#
	def getZwaveNodeTriggerMap(self, trigger, action=u'start'):
		self.logger.debug(u'Mapping or removing Z-wave nodes to/from trigger "%s"' % (trigger.name))
		
		# First, remove all references to trigger
		try:
			self.triggerMap = removeTriggerFromDict(self.triggerMap, trigger.id)
			self.extDebug(u'Removed references to trigger id %s from triggerMap' % (unicode(trigger.id)))
		except:
			self.logger.error(u'Could not remove trigger from triggerMap dictionary')
			raise
		
		# Only add references in triggerMap when starting trigger processing. When disabling triggers this part will be skipped.
		if action == u'start':
			self.extDebug(u'start')
			props = trigger.pluginProps
			m = self.triggerMap
			tmpMap = dict()
			cmdList = set()
			tType = trigger.pluginTypeId
		
			if tType in [u'x71received']:
				includeFilters = self.load(props.get(u'includeFilters',self.store(list())))
				excludeFilters = self.load(props.get(u'excludeFilters',self.store(list())))
		
			CC = eventCC[trigger.pluginTypeId]
		
			if props[u'triggerFor'] == u'all':
				devIter = indigo.devices.iter('indigo.zwave')
			elif props[u'triggerFor'] == u'selected':
				devIter = [indigo.devices[int(d)] for d in props[u'devices']]
			elif props[u'triggerFor'] == u'excludeSelected':
				excludeNodeList = [indigo.devices[int(d)].address for d in props[u'devices']]
				self.extDebug(u'excludeNodeList: %s' % (unicode(excludeNodeList)))
				devIter = [d for d in indigo.devices.iter('indigo.zwave') if d.address not in excludeNodeList]
			else:
				self.logger.error(u'Trigger "%s" seems to be mis-configured, please check settings' % (trigger.name))
				return False
			
			for dev in devIter:
				self.extDebug(u'Mapping trigger for device id %s "%s", node %s' % (unicode(dev.id), unicode(dev.name), unicode(dev.address)))
				addr = int(dev.address)
				#if dev.address not in m: m[dev.address] = dict()
				
				if tType == u'x71received':
					# Inclusion filters, add to triggerMap
					for filter in includeFilters:
						if filter[u'type'] == u'all':
							for alarmType in self.zDefs[CC][u'types']:
								#if u'byte13' not in m[dev.address]: m[dev.address][u'byte13'] = dict()
								#if alarmType not in m[dev.address][u'byte13']: m[dev.address][u'byte13'][alarmType] = dict()
								#if u'byte14' not in m[dev.address][u'byte13'][alarmType]: m[dev.address][u'byte13'][alarmType][u'byte14'] = dict()
								for event in self.zDefs[CC][u'types'][alarmType][u'events']:
									if u'triggers' not in m[addr][CC][u'byte13'][alarmType][u'byte14'][event]:
										m[addr][CC][u'byte13'][alarmType][u'byte14'][event][u'triggers'] = list()
									if trigger.id not in m[addr][CC][u'byte13'][alarmType][u'byte14'][event][u'triggers']:
										m[addr][CC][u'byte13'][alarmType][u'byte14'][event][u'triggers'].append(trigger.id)
									#self.extDebug(u'(Inclusion filter-all alarm types) Mapping trigger type %s, id %s to dev address %s, alarm type %s, event %s' % (unicode(trigger.pluginTypeId), unicode(trigger.id), unicode(dev.address), unicode(alarmType), unicode(event)))
						else:
							alarmType = filter[u'type']
							for event in filter[u'events']:
								if u'triggers' not in m[addr][CC][u'byte13'][alarmType][u'byte14'][event]:
									m[addr][CC][u'byte13'][alarmType][u'byte14'][event][u'triggers'] = list()
								if trigger.id not in m[addr][CC][u'byte13'][alarmType][u'byte14'][event][u'triggers']:
									m[addr][CC][u'byte13'][alarmType][u'byte14'][event][u'triggers'].append(trigger.id)
								#self.extDebug(u'(Inclusion filter) Mapping trigger type %s, id %s  to dev address %s, alarm type %s, event %s' % (unicode(trigger.pluginTypeId), unicode(trigger.id), unicode(dev.address), unicode(alarmType), unicode(event)))
					# Exclusion filters, remove from triggerMap dict
					for filter in excludeFilters:
						alarmType = filter[u'type']
						for event in filter[u'events']:
							if u'triggers' in m[addr][CC][u'byte13'][alarmType][u'byte14'][event]:
								m[addr][CC][u'byte13'][alarmType][u'byte14'][event][u'triggers'] = [tId for tId in m[addr][CC][u'byte13'][alarmType][u'byte14'][event][u'triggers'] if tId != trigger.id]
							#self.extDebug(u'(Exclusion filter)Mapping trigger type %s, id %s  to dev address %s, alarm type %s, event %s' % (unicode(trigger.pluginTypeId), unicode(trigger.id), unicode(dev.address), unicode(alarmType), unicode(event)))
								
				elif tType == u'x80received':
					if props[u'triggerLowBatteryReport'] or props[u'triggerBatteryLevel']:
						#self.extDebug(u'Mapping trigger type %s, id %s to dev address %s, battery report' % (unicode(trigger.pluginTypeId), unicode(trigger.id), unicode(dev.address)))
						if u'triggers' not in m[addr][CC]:
							m[addr][CC][u'triggers'] = list()
						if trigger.id not in m[addr][CC][u'triggers']:
							m[addr][CC][u'triggers'].append(trigger.id)
					else:
						pass
						#self.extDebug(u'Skipping trigger type %s, id %s to dev address %s, battery report' % (unicode(trigger.pluginTypeId), unicode(trigger.id), unicode(dev.address)))
						
				elif tType == u'zOut':
					if props[u'triggerNoAck'] or props[u'triggerSlowAck']:
						#self.extDebug(u'Mapping trigger type %s, id %s to dev address %s, battery report' % (unicode(trigger.pluginTypeId), unicode(trigger.id), unicode(dev.address)))
						if u'triggers' not in m[addr][CC] or len(m[addr][CC][u'triggers']) == 0:
							m[addr][CC][u'triggers'] = list()
						if trigger.id not in m[addr][CC][u'triggers']:
							m[addr][CC][u'triggers'].append(trigger.id)
					else:
						pass
			
		self.logger.debug(u'Finished mapping Z-wave nodes to trigger "%s"' % (trigger.name))			
		#self.extDebug(u'triggerMap: %s' % (unicode(m)))

	#####
	# Check for outgoing triggers, if there is a need to subscribe to outgoing
	#
	def checkOutgoingTriggers(self):
	
		m = self.triggerMap
		
		for addr in m:
			tList = safeGet(m, False, addr, u'zOut', u'triggers')
			if tList:
				self.logger.debug(u'Checking if there are triggers for outgoing z-wave commands: Found')
				return True
				
		self.logger.debug(u'Checking if there are triggers for outgoing z-wave commands: Not found')
		return False
				
	#####
	# Check for dependant plugins, if they are enabled and correct version is installed etc.
	#
	def checkDependantPlugins(self):
		
		self.logger.debug(u'Checking status of other plugins this plugin depends on')
		
		# [<plugin pref for enable of plugin>, <plugin id>, <Friendly name>, <min plugin version>]
		pluginList = [
			[u'plugin-betteremail', u'com.flyingdiver.indigoplugin.betteremail', u'Better E-mail', u'7.1.0']
			]
			
		for plug in pluginList:
			
			usePlugin = self.pluginPrefs.get(plug[0], False)
			
			self.logger.debug(u'Checking plugin "%s"' % plug[2])
		
			try:
				if not usePlugin:
					raise
				try:
					indigoPlug = indigo.server.getPlugin(plug[1])
					if not indigoPlug.isEnabled():
						raise ImportError(u'Plugin "%s" is not enabled, please install/enable, and re-enable in ZEAL plugin preferences' % plug[2])
					if len(indigoPlug.pluginVersion) == 0 or indigoPlug.pluginVersion < plug[3]:
						raise ImportError(u'Plugin "%s" version %s is less than ZEAL requires (%s), please update the plugin.\nUse of this plugin in ZEAL has been disabled' % (plug[2], indigoPlug.pluginVersion, plug[3]))
						
					# Plugin specific checks:
					if plug[1] == u'com.flyingdiver.indigoplugin.betteremail':
						smtpDevId = self.pluginPrefs.get(u'plugin-betteremail-smtpdevice', u'')
						if len(smtpDevId) == 0:
							raise ImportError(u'You need to specify a valid "%s" SMTP device in ZEAL plugin preferences' % plug[2])
						else:
							try:
								smtpDev = indigo.devices[int(smtpDevId)]
								if not smtpDev.enabled:
									raise
							except:
								raise ImportError(u'The specified "%s" SMTP device could not be loaded, please check\nZEAL plugin preferences and that the SMTP device is enabled')					
				except ImportError as e:
					self.logger.error(e)
					raise
				except:
					self.logger.error(u'Could not load plugin "%s". Please install and re-enable in ZEAL plugin preferences' % plug[2])
					raise
			except:
				# Common code for disabling use of the plugin
				if usePlugin: # configured to use plugin, so some error happened
					self.logger.debug(u'Disabling use of plugin "%s" in plugin prefs' % plug[2])
					if len(indigoPlug.pluginSupportURL) > 0:
						self.logger.info(u'"%s" support/install link: %s' % (plug[2], indigoPlug.pluginSupportURL))
				else:
					self.logger.debug(u'Not configured to use plugin "%s"' % plug[2])
				self.pluginPrefs[plug[0]] = False
				if plug[1] in self.dependantPlugins:
					del self.dependantPlugins[plug[1]]
			else:
				# Plugin is successfully initialized, add to dict of enabled plugins
				self.logger.debug(u'Plugin "%s" successfully checked' % plug[2])
				self.dependantPlugins[plug[1]] = indigoPlug

		
	########################################
	# Actions
	########################################

	def resetTriggerBatteryLevel(self, action):
		self.extDebug(u'CALL resetTriggerBatteryLevel')
		self.extDebug(u'action: %s' % unicode(action))
		
		props = action.props
				
		try:
			trigger = indigo.triggers[int(props[u'trigger'])]
		except:
			self.logger.error(u'Reset trigger battery level: Could not get selected trigger from Indigo')
			return False
					
		pluginProps = trigger.pluginProps
		
		if props.get(u'resetDevice', '') == u'all':
			self.logger.debug(u'Resetting battery level trigger for all devices, trigger id %d' % (trigger.id))
			try:
				pluginProps[u'lowBatteryTriggeredNodes'] = self.store(dict())
				pluginProps[u'batteryLevelTriggeredNodes'] = self.store(dict())
				trigger.replacePluginPropsOnServer(pluginProps)
				self.logger.info(u'Reset low battery and battery level trigger for all devices, trigger id %d' % (trigger.id))
			except:
				self.logger.error(u'Could not reset low battery and battery level trigger, trigger "%s", all devices' % (unicode(trigger.name)))
				raise
		else:
		
			try:
				dev = indigo.devices[int(props.get(u'resetDevice', ''))]
			except:
				self.logger.error(u'Reset trigger battery level: Could not get selected device from Indigo, trigger "%s", device id %s' % (unicode(trigger.name), unicode(props.get(u'resetDevice', ''))))
				return False				
			
			self.logger.info(u'Resetting low battery and battery level trigger for device "%s" on trigger "%s"' % (unicode(dev.name), unicode(trigger.name)))

			lowBatteryTriggeredNodes = self.load(pluginProps.get(u'lowBatteryTriggeredNodes', self.store(dict())))
			batteryLevelTriggeredNodes = self.load(pluginProps.get(u'batteryLevelTriggeredNodes', self.store(dict())))
			replacePluginProps = False
			#self.extDebug(u'triggeredDeviceList before: %s' % unicode(triggeredDeviceList))
		
			if unicode(dev.address) in lowBatteryTriggeredNodes:
				self.logger.info(u'Device node %03d found in list of triggered devices on low battery for selected trigger' % (int(dev.address)))
				try:
					del lowBatteryTriggeredNodes[unicode(dev.address)]
					pluginProps[u'lowBatteryTriggeredNodes'] = self.store(lowBatteryTriggeredNodes)
					#self.extDebug(u'triggeredDeviceList after: %s' % unicode(triggeredDeviceList))
					#trigger.replacePluginPropsOnServer(pluginProps)
					self.logger.info(u'Reset device "%s" low battery  trigger, trigger id %d' % (dev.name, trigger.id))
					replacePluginProps = True
				except:
					self.logger.error(u'Could not reset low battery trigger, trigger "%s", device "%s"' % (unicode(trigger.name), unicode(dev.name)))
					raise
			else:
				self.logger.info(u'Device not found in list of devices triggered on low battery for selected trigger, not performing anything')	
				
			if unicode(dev.address) in batteryLevelTriggeredNodes:
				self.logger.info(u'Device node %03d found in list of triggered devices on battery level for selected trigger' % (int(dev.address)))
				try:
					del batteryLevelTriggeredNodes[unicode(dev.address)]
					pluginProps[u'batteryLevelTriggeredNodes'] = self.store(batteryLevelTriggeredNodes)
					#self.extDebug(u'triggeredDeviceList after: %s' % unicode(triggeredDeviceList))
					#trigger.replacePluginPropsOnServer(pluginProps)
					self.logger.info(u'Reset device "%s" battery level trigger, trigger id %d' % (dev.name, trigger.id))
					replacePluginProps = True
				except:
					self.logger.error(u'Could not reset battery level trigger, trigger "%s", device "%s"' % (unicode(trigger.name), unicode(dev.name)))
					raise
			else:
				self.logger.info(u'Device not found in list of devices triggered on battery level for selected trigger, not performing anything')	
				
			if replacePluginProps:
				trigger.replacePluginPropsOnServer(pluginProps)
				
		
		return True

	# Print z-wave node statistics to log or e-mail
	def printNodeStatsToLogEmail(self, action = None):
	
		self.logger.debug(u'Outputting Z-wave node statistics to indigo log and/or e-mail')
	
		if not self.keepStats:
			self.logger.error(u'Plugin is not configured to keep z-wave node statistics, check plugin preferences')
			return
		else:
		
			if action is not None:
			
				self.logger.debug(u'Called by action')
			
				props = action.props
		
				if props[u'includeFor'] == u'all':
					devList = None
				elif props[u'includeFor'] == u'selected':
					devList = [indigo.devices[int(d)].id for d in props[u'devices']]
				elif props[u'includeFor'] == u'excludeSelected':
					excludeNodeList = [indigo.devices[int(d)].address for d in props[u'devices']]
					devList = [d.id for d in indigo.devices.iter('indigo.zwave') if d.address not in excludeNodeList]
					#devList = [d.id for d in indigo.devices.iter('indigo.zwave') if unicode(d.id) not in props[u'devices']]
					
				if props[u'includedColumns'] == u'all':
					columnOrder = ['node', 'device'] + [d[0] for d in sorted(nodeStatsConf, key=itemgetter(2))]
					headings = None
				else:
					columnOrder = list()
					headings = list()
					if u'node' in props[u'columns']:
						columnOrder.append('node')
						headings.append('Node')
					if u'device' in props[u'columns']:
						columnOrder.append('device')
						headings.append('Device')
												
					for prop in sorted(nodeStatsConf, key=itemgetter(2)):
						if prop[0] in props[u'columns']:
							columnOrder.append(prop[0])
							headings.append(prop[1])

				orderByColumn = 1
				for i, c in enumerate(columnOrder):
					if c == props.get(u'orderBy', u''):
						orderByColumn = i
							
				defaultValue = props.get(u'defValue', u'-')
				email = props.get(u'email', False)
				log = props.get(u'indigoLog', True)
					
			else:
				self.logger.debug(u'Called by menu item')
				devList = None
				columnOrder = None
				headings = None
				defaultValue = u'-'
				log = True
				email = False
				orderByColumn = 1
				
			headers, statData = self.getNodeStats(deviceList=devList, columnOrder=columnOrder, headers=headings)
			if len(statData) > 0:
				self.logger.debug(u'Found z-wave node statistics, outputting...')
				statData = sorted(statData, key=itemgetter(orderByColumn))
				#output = tabulate.tabulate(statData, headers=headers, floatfmt='.0f', missingval=defaultValue)
				
				if log:
					self.logger.info(u'\n' + tabulate.tabulate(statData, headers=headers, floatfmt='.0f', missingval=defaultValue))
					
				if email:
				
					emailAdr = self.substitute(props.get(u'emailAddress', u''))
					emailSubject = self.substitute(props.get(u'emailSubject', u'Indigo ZEAL Z-wave node statistics'))
					emailBody = self.substitute(props.get(u'emailBody', u''))
				
					if u'com.flyingdiver.indigoplugin.betteremail' in self.dependantPlugins:
						# Sending with Better E-mail plugin, using HTML format
						
						if len(emailBody) > 0:
							emailBody = u'\n<p>' + emailBody + u'</p>\n'
						emailMessage = \
							u'<html>\n<body>\n' + emailBody + \
							tabulate.tabulate(statData, headers=headers, floatfmt='.0f', missingval=defaultValue, tablefmt='html') + \
							u'\n</body>\n</html>'
						
						self.dependantPlugins[u'com.flyingdiver.indigoplugin.betteremail'].executeAction(u'sendEmail',
							deviceId=int(self.pluginPrefs.get(u'plugin-betteremail-smtpdevice', 0)),
							props={
								u'emailFormat' 		: u'html',
								u'emailTo'			: emailAdr,
								u'emailSubject'		: emailSubject,
								u'emailMessage'		: emailMessage })
								
					
					else:
						# Not using Better E-mail, use plain text with Indigo
						emailMessage = emailBody + u'\n\n' + \
							tabulate.tabulate(statData, headers=headers, floatfmt='.0f', missingval=defaultValue, tablefmt='plain')
						indigo.server.sendEmailTo(emailAdr, subject=emailSubject, body=emailMessage)

			else:
				self.logger.info(u'No statistics has been gathered yet')

	def getNodeStats(self, deviceList = None, columnOrder = None, headers = None, defValue=None):
	
		##self.nodeStats	 nodeId<str> : [numIn, numOut, numNoAck, numSlowAckTriggers, minAckTime, maxAckTime, avgAckTime, numNotifications, numBatteryReports]
		
		if headers is None:
			#headers = [u'Node', u'Device', u'Num Cmds:\nIn', u'Out', u'Notifications', u'Batt.reports', u'Number of:\nNo Ack.', u'Slow Ack', u'AckTime (ms):\nMin', u'Max', u'Avg']
			#headers = [u'Node', u'Device', u'In', u'Out', u'Notif.', u'Batt.', u'No Ack', u'Slow Ack', u'Ack min.', u'Ack max', u'Ack avg']
			headers = [u'Node', u'Device']
			for c in sorted(nodeStatsConf, key=itemgetter(2)):
				headers.append(c[1])
			
		#if defValue is None:
		#	defValue = u'-'
		
		# get a list of "columns", with prop id, 'in', 'out', etc.
		if columnOrder is None:
			columnOrder = ['node', 'device'] + [d[0] for d in sorted(nodeStatsConf, key=itemgetter(2))]
			
		# Get a list with list index in self.nodeStats, to iterate over
		columnIter = list()
		for prop in columnOrder:
			if prop in ['node', 'device']:
				columnIter.append(prop)
				continue
			for x, e in enumerate(nodeStatsConf):
				if e[0] == prop:
					columnIter.append(x)
					break
			
		if deviceList is None:
			nodeIter = [n for n in self.zNodes]
		else:
			nodeIter = list()
			for n in self.zNodes:
				for e in self.zNodes[n]:
					if self.zNodes[n][e].id in deviceList:
						nodeIter.append(n)
						break
						
		self.extDebug(u'nodeIter: %s' % unicode(nodeIter))
		
		stats = list()
		
		iterEndpoint = [None,1,2,3,4,5,6,7,8,9,10]
		
		for nodeId in nodeIter: #nodeId is unicode
		
			rowList = list()
						
			if nodeId not in self.nodeStats:
				continue 
			
			for endpoint in iterEndpoint:
				if endpoint in self.zNodes[nodeId]:
					dev = self.zNodes[nodeId][endpoint]
					break # Only include devices with "lowest" endpoint
			else:
				break # Skip the node if it is not found in self.zNodes
			
			for i in columnIter: # i = index of self.nodeStats
			
				if i == 'node':
					try:
						rowList.append(int(nodeId))
					except:
						rowList.append(nodeId)
					continue
				elif i == 'device':
					rowList.append(dev.name)
					continue
				
				value = self.nodeStats[nodeId][i]
				if value == 0:
					value = defValue
				rowList.append(value)
				
			stats.append(rowList)
				
		return headers, stats
		
	def resetNodeStats(self, action = None):
	
		self.logger.info(u'Resetting all Z-wave node statistics')
		self.nodeStats = dict()
		self.pluginPrefs[u'nodeStats'] = self.store(self.nodeStats)
			

	########################################
	# UI List generators and callbackmethods
	########################################
	
	# X71 trigger/event
	# x71received

	# get available filters, commands etc.
	def getUIList(self, filter="", valuesDict=None, typeId="", targetId=0):
		self.extDebug(u'CALL getUIList')
		self.extDebug(u'valuesDict: %s' % unicode(valuesDict))
		self.extDebug(u'filter: %s' % filter)
		self.extDebug(u'typeId: %s' % typeId)
		self.extDebug(u'targetId: %s' % targetId)
		
		if filter in [u'includeFilters', u'excludeFilters']:
			myArray = [
				(u"_blank",u" "),
				(u"_createNew",u"Create new filter...")]
		elif filter in [u'alarmTypesInclude', u'eventsInclude', u'eventsExclude', u'x80resetDeviceList']:
			myArray = [
				(u"all",u"All")]
		elif filter in [u'alarmTypesExclude', u'zDeviceList', u'nodeStatsColumns', u'nodeStatsColumnsOrder']:
			myArray = list()
			
		tmpArray = list()
			
		if filter == u'includeFilters' or filter == u'excludeFilters':
			if filter in valuesDict:
				self.extDebug(u'%s: %s' % (unicode(filter), unicode(valuesDict[filter])))
				filterList = self.load(valuesDict.get(filter, self.store(list())))
				for filterNum, filterDict in enumerate(filterList):
					#self.logger.debug(u'k: %s, v: %s' % (k,v))
					tmpArray.append( (filterNum,filterDict['name']) )
		
		elif filter == u'alarmTypesInclude' or filter == u'alarmTypesExclude':
			for cmdType, cmdTypeDict in self.zDefs[u'0x71'][u'types'].items():
				tmpArray.append( (cmdType,unicode(cmdType) + ' - ' + safeGet(cmdTypeDict, u'%s - Unspecified type' % unicode(cmdType), u'description')) ) 
		
		elif filter == u'eventsInclude' or filter == u'eventsExclude':
			if filter == u'eventsInclude': typeKey = u'includeFilterType'
			elif filter == u'eventsExclude': typeKey = u'excludeFilterType'
			
			if typeKey not in valuesDict:
				myArray = list()
				pass
			elif valuesDict[typeKey] == u'all':
				self.extDebug(u'Selected all alarm types')
			elif valuesDict[typeKey] == u'':
				myArray = list()
			elif not valuesDict[typeKey] in self.zDefs[u'0x71'][u'types']:
				myArray = list()
				self.logger.warn(u'Invalid or no selected alarm/notification type')
			else:
				myArray = [(u"all",u"All")]
				for event, eventDict in self.zDefs[u'0x71'][u'types'][valuesDict[typeKey]][u'events'].items():
					tmpArray.append( (event,unicode(event) + u' - ' + safeGet(eventDict, u'Unspecified event', u'description')) )
		
		elif filter == u'x80resetDeviceList':
			try:
				if u'trigger' in valuesDict:
					trigger = indigo.triggers[int(valuesDict[u'trigger'])]
				else:
					self.extDebug(u'no trigger selected')
					return myArray
			except:
				self.logger.error(u'Could not get selected trigger from Indigo')
				return myArray
			
			props = trigger.pluginProps
			devArray = list()
			
			if props[u'triggerFor'] == u'all':
				devIter = indigo.devices.iter('indigo.zwave')
			elif props[u'triggerFor'] == u'selected':
				devIter = [indigo.devices[int(d)] for d in props[u'devices']]
			elif props[u'triggerFor'] == u'excludeSelected':
				devIter = [d for d in indigo.devices.iter('indigo.zwave') if unicode(d.id) not in props[u'devices']]
			else:
				self.logger.warn(u'Trigger seems to be mis-configured, please check trigger configuration')
				return myArray

			for dev in devIter:
				devArray.append ( (dev.id,dev.name) )
				
			sortedDevArray = sorted ( devArray, key = operator.itemgetter(1))

			myArray = myArray + sortedDevArray
			
		# FIX if some way to get 'main' device exists/ is created
		elif filter == u'zDeviceList':
			devArray = list()
			iterEndpoint = [None,1,2,3,4,5,6,7,8,9,10]
			for node in self.zNodes:
				for endpoint in iterEndpoint:
					if endpoint in self.zNodes[node]:
						dev = self.zNodes[node][endpoint]
						devArray.append( (dev.id, dev.name) )
						break # Only include devices with "lowest" endpoint
			myArray = sorted (devArray, key = operator.itemgetter(1))	
				
		elif filter in  [u'nodeStatsColumnsOrder', u'nodeStatsColumns']:
			myArray.append( (u'node', u'Node Id') )
			myArray.append( (u'device', u'Device Name') )
			for prop in nodeStatsConf:
				myArray.append( (prop[0], prop[1]) )
			

		
		tmpArray.sort()
		myArray = myArray + tmpArray
					
		self.extDebug(u'myArray: %s' % unicode(valuesDict))

		return myArray
	
	def x71receivedIncludeFilterChangedFilterSelection(self, valuesDict=None, typeId="", targetId=0):
		valuesDict = self.selectedFilterChanged(u'includeFilter', valuesDict, typeId, targetId)
		return valuesDict
	
	def x71receivedExcludeFilterChangedFilterSelection(self, valuesDict=None, typeId="", targetId=0):
		valuesDict = self.selectedFilterChanged(u'excludeFilter', valuesDict, typeId, targetId)
		return valuesDict

	def selectedFilterChanged(self, type, valuesDict=None, typeId="", targetId=0):
		self.extDebug(u'CALL selectedFilterChanged')
		self.extDebug(u'valuesDict: %s' % unicode(valuesDict))
		self.extDebug(u'typeId: %s' % typeId)
		self.extDebug(u'targetId: %s' % targetId)
		self.extDebug(u'type: %s' % type)
		
		if type == u'includeFilter':
			typeC = u'IncludeFilter'
		elif type == u'excludeFilter':
			typeC = u'ExcludeFilter'
		else:
			self.logger.error(u'Unexpected filter type in selectedFilterChanged')
			return valuesDict

		# Clear all previous messages
		valuesDict[u'includeFilterStatus'] = ''
		valuesDict[u'showIncludeFilterStatus'] = False
		valuesDict[u'excludeFilterStatus'] = ''
		valuesDict[u'showExcludeFilterStatus'] = False

		if valuesDict[u'selected'+typeC] == u'_createNew' or valuesDict[u'selected'+typeC] == u'_blank':
			self.logger.debug(u'New filter selected, clearing values from UI')
			valuesDict[type+u'Name'] = u''
			valuesDict[type+u'Type'] = u''
			valuesDict[type+u'Events'] = list()
		else:
			self.logger.debug(u'Existing filter selected, retrieving stored values')
			if type+u's' in valuesDict:
				filterList = self.load(valuesDict.get(type+u's', self.store(list())))
				currFilter = filterList[int(valuesDict[u'selected'+typeC])]
				valuesDict[type+u'Name'] = currFilter[u'name']
				valuesDict[type+u'Type'] = currFilter[u'type']
				valuesDict[type+u'Events'] = currFilter[u'events']
				valuesDict[type+u'Status'] = ''
				valuesDict[u'show'+typeC+u'Status'] = False
				self.logger.debug(u'Retrieved selected filter "%s"' % (currFilter[u'name']))
			else:
				valuesDict[type+u'Status'] = 'Could not get selected filter'
				valuesDict[u'show'+typeC+u'Status'] = True
				self.logger.error(u'Could not get stored values for selected filter in selectedFilterChanged')
	
		self.extDebug(u'return valuesDict: %s' % unicode(valuesDict))
		return valuesDict
		
		
	def x71receivedIncludeFilterChangedTypeSelection(self, valuesDict=None, typeId="", targetId=0):
		self.extDebug(u'CALL x71receivedIncludeFilterChangedTypeSelection')
		self.extDebug(u'valuesDict: %s' % unicode(valuesDict))
		self.extDebug(u'typeId: %s' % typeId)
		self.extDebug(u'targetId: %s' % targetId)
		
		valuesDict[u'includeFilterEvents'] = list()
	
		return valuesDict
		
	def x71receivedExcludeFilterChangedTypeSelection(self, valuesDict=None, typeId="", targetId=0):
		self.extDebug(u'CALL x71receivedExcludeFilterChangedTypeSelection')
		self.extDebug(u'valuesDict: %s' % unicode(valuesDict))
		self.extDebug(u'typeId: %s' % typeId)
		self.extDebug(u'targetId: %s' % targetId)
		
		valuesDict[u'excludeFilterEvents'] = list()
	
		return valuesDict
		
		
	# 	def selectedTriggerFilterChangedEventSelection(self, valuesDict=None, typeId="", targetId=0):
	# 		self.extDebug(u'CALL selectedTriggerFilterChangedEventSelection')
	# 		self.extDebug(u'valuesDict: %s' % unicode(valuesDict))
	# 		self.extDebug(u'typeId: %s' % typeId)
	# 		self.extDebug(u'targetId: %s' % targetId)
	# 	
	# 		#self.logger.debug(u'return valuesDict: %s' % unicode(valuesDict))
	# 		return valuesDict

	def x71receivedSelectedIncludeFilterSave(self, valuesDict=None, typeId="", targetId=0):
		valuesDict = self.selectedFilterSave(u'includeFilter', valuesDict, typeId, targetId)
		return valuesDict
		
	def x71receivedSelectedExcludeFilterSave(self, valuesDict=None, typeId="", targetId=0):
		valuesDict = self.selectedFilterSave(u'excludeFilter', valuesDict, typeId, targetId)
		return valuesDict		
		
	def selectedFilterSave(self, type, valuesDict=None, typeId="", targetId=0):
		self.extDebug(u'CALL selectedFilterSave')
		self.extDebug(u'valuesDict: %s' % unicode(valuesDict))
		
		errorMsg = list()
		valError = False
		filterAction = ''
		
		if type == u'includeFilter':
			typeC = u'IncludeFilter'
		elif type == u'excludeFilter':
			typeC = u'ExcludeFilter'
		else:
			self.logger.error(u'Unexpected filter type in selectedFilterSave')
			return valuesDict

		if valuesDict[u'selected'+typeC] == u'_createNew': filterAction = 'new' # Saving new filter
		elif valuesDict[u'selected'+typeC] != u'_blank': filterAction = 'modify' #Modifying existing filter
		elif valuesDict[u'selected'+typeX] == u'_blank': filterAction = 'blank' #No filter selected
		
		if filterAction == 'new' or filterAction == 'modify':
			filterList = self.load(valuesDict.get(type+u's', self.store(list())))
			
			if filterAction == 'new':
				self.logger.debug(u'Saving new filter..')
				currFilter = {}
			elif filterAction == 'modify':
				self.logger.debug(u'Modifying existing filter..')
				currFilter = filterList[int(valuesDict[u'selected'+typeC])]
			
			# Filter name
			if len(valuesDict[type+u'Name']) > 0:
				currFilter[u'name'] = valuesDict[type+u'Name']
			else:
				errorMsg.append(u'Please specify a filter name')
				valError = True
			
			# Filter alarm types
			if not valuesDict[type+u'Type'] in self.zDefs[u'0x71'][u'types'] and valuesDict[type+u'Type'] != u'all':
				errorMsg.append(u'Invalid or no alarm/notification type selected')
				valError = True
			currFilter[u'type'] = valuesDict[type+u'Type']
			
			# Filter events
			if u'all' in valuesDict[type+u'Events']:
				currFilter[u'events'] = u'all'
			elif len(valuesDict[type+u'Events']) > 0:
				currFilter[u'events'] = list(valuesDict[type+u'Events']) # need to convert indigo list to python list, for json
			else:
				errorMsg.append(u'Invalid or no event selected')
				valError = True
			
			self.extDebug(u'currFilter: %s' % unicode(currFilter))
			
			if valError:
				valuesDict[type+u'Status'] = '\n'.join(errorMsg)
				valuesDict[u'show'+typeC+u'Status'] = True
			else:
				try:
					if filterAction == 'new':
						filterList.append(currFilter)
						valuesDict[type+u's'] = self.store(filterList)
						valuesDict[u'selected'+typeC] = unicode(len(filterList)-1)
						valuesDict[type+u'Status'] = 'Saved'
						valuesDict[u'show'+typeC+u'Status'] = True
					elif filterAction == 'modify':
						valuesDict[type+u's'] = self.store(filterList)
						valuesDict[type+u'Status'] = 'Modified'
						valuesDict[u'show'+typeC+u'Status'] = True
					self.logger.debug(u'Saved filter "%s"' % (currFilter[u'name']))
				except:
					self.logger.exception(u'Could not save filter: %s' % (unicode(currFilter)))
					
		elif filterAction == 'blank':
			valuesDict[type+u'Status'] = 'Please select a filter before saving'
			valuesDict[u'show'+typeC+u'Status'] = True
			
		self.extDebug(u'valuesDict: %s' % unicode(valuesDict))
		return valuesDict
		
	def x71receivedSelectedIncludeFilterDelete(self, valuesDict=None, typeId="", targetId=0):
		valuesDict = self.selectedFilterDelete(u'includeFilter', valuesDict, typeId, targetId)
		return valuesDict
		
	def x71receivedSelectedExcludeFilterDelete(self, valuesDict=None, typeId="", targetId=0):
		valuesDict = self.selectedFilterDelete(u'excludeFilter', valuesDict, typeId, targetId)
		return valuesDict		
		
	def selectedFilterDelete(self, type, valuesDict=None, typeId="", targetId=0):
		self.extDebug(u'CALL selectedFilterDelete')
		self.extDebug(u'valuesDict: %s' % unicode(valuesDict))
		
		errorMsg = list()
		valError = False
		filterAction = ''
		
		if type == u'includeFilter':
			typeC = u'IncludeFilter'
		elif type == u'excludeFilter':
			typeC = u'ExcludeFilter'
		else:
			self.logger.error(u'Unexpected filter type in selectedFilterSave')
			return valuesDict
			
		filterList = self.load(valuesDict.get(type+u's', self.store(list())))
		
		try:
			deletedFilter = filterList.pop(int(valuesDict[u'selected'+typeC]))
			self.logger.debug(u'Deleted filter "%s"'  % (deletedFilter[u'name']))
			valuesDict[type+u's'] = self.store(filterList)
			valuesDict[type+u'Status'] = 'Filter "%s" deleted' % (deletedFilter[u'name'])
			valuesDict[u'show'+typeC+u'Status'] = True
			# Clear values from UI
			valuesDict[type+u'Name'] = ''
			valuesDict[type+u'Type'] = ''
			valuesDict[type+u'Events'] = list()
			valuesDict[u'selected'+typeC] = u'_blank'
		except:
			self.logger.exception(u'Could not delete filter')
			valuesDict[type+u'Status'] = 'Error: Could not delete filter'
			valuesDict[u'show'+typeC+u'Status'] = True
			
		return valuesDict
		

	###############################
	# x80received
	###############################
		
	def x80receivedResetTriggerChanged(self, valuesDict=None, typeId="", targetId=0):
		# FIX, device list won't update without this function, don't understand quite why
		return valuesDict

	###############################
	# printNodeStatsToLogOrEmail
	###############################

	########################################
	# UI VALIDATION
	########################################	
	
	# Validate plugin prefs changes:
	def validatePrefsConfigUi(self, valuesDict):
		self.extDebug(u'CALL validatePrefsConfigUI, valuesDict: %s' % unicode(valuesDict))
		
		errorDict = indigo.Dict()
		
		for varPref in variableEnablePrefs:
			if valuesDict.get(varPref, False):
				if len(valuesDict.get(varPref + u'Variable', u'')) == 0:
					errorDict[varPref + u'Variable'] = u'Please select a variable'
				else:
					try:
						var = indigo.variables[int(valuesDict.get(varPref + u'Variable'))]
					except:
						errorDict[varPref + u'Variable'] = u'Invalid variable selected'
						
			
		if len(errorDict) > 0:
			return (False, valuesDict, errorDict)
		else:
			return (True, valuesDict)
			
	def validateEventConfigUi(self, valuesDict=None, typeId='', eventId=0):
		# Do your validation logic here
		errorDict = indigo.Dict()
		# 		errorDict["someKey"] = "The value of this field must be from 1 to 10"
		# 		errorDict[“showAlertText”] = “Some very descriptive message to your user that will help them solve the validation problem.”
		
		if typeId == u'x71received':
			# Make sure selected values are reset
			valuesDict[u'includeFilterStatus'] = ''
			valuesDict[u'showIncludeFilterStatus'] = False
			valuesDict[u'includeFilterName'] = ''
			valuesDict[u'includeFilterType'] = ''
			valuesDict[u'includeFilterEvents'] = list()
			valuesDict[u'selectedIncludeFilter'] = u'_blank'
		
			valuesDict[u'excludeFilterStatus'] = ''
			valuesDict[u'showExcludeFilterStatus'] = False
			valuesDict[u'excludeFilterName'] = ''
			valuesDict[u'excludeFilterType'] = ''
			valuesDict[u'excludeFilterEvents'] = list()
			valuesDict[u'selectedExcludeFilter'] = u'_blank'
		
		if valuesDict[u'triggerFor'] == u'selected':
			if len(valuesDict.get(u'devices', list())) == 0:
				errorDict[u'devices'] = u'Please select at least one device'
			
		if typeId == u'x80received':
			if (not valuesDict[u'triggerLowBatteryReport']) and (not valuesDict[u'triggerBatteryLevel']):
				errorDict[u'triggerBatteryLevel'] = u'Please select at least one trigger method'
				errorDict[u'triggerLowBatteryReport'] = u'Please select at least one trigger method'
				
			if valuesDict[u'triggerBatteryLevel']:
				try:
					triggerLevel = int(valuesDict[u'batteryLevel'])
					if (triggerLevel < 0 or triggerLevel > 100):
						errorDict[u'batteryLevel'] = u'Please type a battery level between 0 and 100'
				except ValueError:
					errorDict[u'batteryLevel'] = u'Please type a valid battery level (0-100)'
					
			if valuesDict[u'batteryLevelResetOn'] == u'levelAbove':
				try:
					resetLevel = int(valuesDict[u'batteryLevelResetLevel'])
					if resetLevel <= triggerLevel:
						errorDict[u'batteryLevelResetLevel'] = u'Please type a reset level that is higher than the trigger level'
					if resetLevel < 0 or resetLevel > 100:
						errorDict[u'batteryLevelResetLevel'] = u'Please type a reset level between 0 and 100'
				except ValueError:
					errorDict[u'batteryLevelResetLevel'] = u'Please type a valid battery level (0-100)'
					
			if valuesDict[u'batteryLevelResetOn'] == u'onTime':
				try:
					numHours = int(valuesDict[u'batteryLevelResetTime'])
					if numHours < 1 or numHours > 5000:
						errorDict[u'batteryLevelResetTime'] = u'Please type a number of hours between 1 and 5000'
				except ValueError:
					errorDict[u'batteryLevelResetTime'] = u'Please type a valid battery level (1-5000)'
						
		if typeId == u'zOut':
			if (not valuesDict[u'triggerNoAck']) and (not valuesDict[u'triggerSlowAck']):
				errorDict[u'triggerNoAck'] = u'Please select at least one trigger method'
				errorDict[u'triggerSlowAck'] = u'Please select at least one trigger method'
				
			if valuesDict[u'triggerSlowAck']:
				try:
					triggerLevel = int(valuesDict[u'ackTime'])
					if (triggerLevel < 100 or triggerLevel > 10000):
						errorDict[u'ackTime'] = u'Please type a response time between 100 and 10000'
				except ValueError:
					errorDict[u'ackTime'] = u'Please type a valid integer response time (100-10000)'
					
			# FIX validation for not saving filter
			# FIX improve showAlertText:
			#errorDict['showAlertText'] = u'Test!'
		
		if len(errorDict) > 0:
			errorDict[u'showAlertText'] = u'\n'.join([value for key, value in errorDict.items() if key != u'showAlertText'])
			return (False, valuesDict, errorDict)
		else:
			return (True, valuesDict)
		
	def validateActionConfigUi(self, valuesDict=None, typeId='', deviceId=0):
		self.extDebug(u'CALL validateActionConfigUi, valuesDict: %s' % unicode(valuesDict))
		self.extDebug(u'typeId: %s' % typeId)
		self.extDebug(u'deviceId: %s' % deviceId)
		
		errorDict = indigo.Dict()
	
		if typeId == u'resetTriggerBatteryLevel':
			# Check trigger
			try:
				if u'trigger' in valuesDict and len(valuesDict[u'trigger']) > 0:
					trigger = indigo.triggers[int(valuesDict[u'trigger'])]
				else:
					self.logger.warn(u'No trigger selected')
					errorDict[u'trigger'] = u'Please select a trigger'
					return (False, valuesDict, errorDict)
			except:
				self.logger.error(u'Could not get selected trigger from Indigo')
				errorDict[u'trigger'] = u'Could not get selected trigger from Indigo'
				return (False, valuesDict, errorDict)
				
			try:
				if u'all' in valuesDict.get(u'resetDevice', list()):
					return (True, valuesDict, errorDict)
				elif u'resetDevice' in valuesDict and len(valuesDict[u'resetDevice']) > 0:
					dev = indigo.devices[int(valuesDict[u'resetDevice'])]
				else:
					self.logger.warn(u'No device selected')
					errorDict[u'resetDevice'] = u'Please select a device'
					return (False, valuesDict, errorDict)
			except:
				self.logger.error(u'Could not get selected device from Indigo')
				errorDict[u'resetDevice'] = u'Could not get selected device from Indigo'
				return (False, valuesDict, errorDict)
				
		elif typeId == u'printNodeStatsToLogOrEmail':
			
			if (not valuesDict[u'indigoLog']) and (not valuesDict[u'email']):
				errorDict[u'indigoLog'] = u'Please select at least one delivery method'
				errorDict[u'email'] = u'Please select at least one delivery method'
				
			if valuesDict[u'email']:
				if len(valuesDict[u'emailAddress']) == 0:
					errorDict[u'emailAddress'] = u'Please specify an e-mail address'
				if not self.validateEmail(valuesDict[u'emailAddress']):
					errorDict[u'emailAddress'] = u'Invalid e-mail address specified'
					
			if valuesDict[u'includeFor'] in [u'selected', u'excludeSelected']:
				if len(valuesDict[u'devices']) == 0:
					errorDict[u'devices'] = u'Please choose at least one device'
					
			if valuesDict[u'includedColumns'] == u'selected':
				if len(valuesDict[u'columns']) == 0:
					errorDict[u'columns'] = u'Please choose at least one column to be included'
					
			if len(valuesDict[u'orderBy']) > 0:
				if valuesDict[u'includedColumns'] == u'selected':
					if valuesDict[u'orderBy'] not in valuesDict[u'columns']:
						errorDict[u'orderBy'] = u'The selected order by column needs to be selected as an included column'
					
			if len(errorDict) > 0:
				errorDict[u'showAlertText'] = u'\n'.join(set([value for key, value in errorDict.items()]))
				return (False, valuesDict, errorDict)
				
					
				
		return (True, valuesDict)
		
	# def getDeviceConfigUiValues():
	# possible to get values of device config UI?	
		
	# Catch changes to config prefs
	def closedPrefsConfigUi(self, valuesDict, userCancelled):
		self.extDebug(u'CALL closedPrefsConfigUi, valuesDict: %s' % unicode(valuesDict))
		self.extDebug(u'CALL closedPrefsConfigUi, userCancelled: %s' % unicode(userCancelled))
		
		self.setUpdatePluginPrefs(True)

		# FIX DO VALIDATION
		self.pluginConfigErrorState = False
		
	########################################
	# HELPERS
	########################################	
	

	########################################
	# Store and load information
	def store(self, val):
		return json.dumps(val)
	
	def load(self, val):
		return json.loads(val)
		
	# Validate e-mail addres:
	def validateEmail(self, emailStr):
		# very simple e-mail validation
		if len(emailStr) >= 7:
			self.extDebug(u'E-mail over 6 characters')
			pos = emailStr.find(u'@',1)
			if pos != -1:
				self.extDebug(u'@ found in e-mail')
				pos2 = emailStr.find(u'.',pos)
				if pos2 != -1:
					self.extDebug(u'. found in e-mail after @')
					return True

		return False

