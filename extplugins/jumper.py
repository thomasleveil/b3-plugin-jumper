#
# Jumper Plugin for BigBrotherBot(B3) (www.bigbrotherbot.net)
# Copyright (C) 2013 Fenix <fenix@urbanterror.info)
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

__author__ = 'Fenix - http://www.urbanterror.info'
__version__ = '2.3'

import b3
import b3.plugin
import b3.events
import urllib2
import json
import time
import datetime
import os
import re
    
class JumperPlugin(b3.plugin.Plugin):
    
    _adminPlugin = None
    
    _demoRecord = False
    _minLevelDelete = 80
    _mapData = { }
    
    _demoRecordRegEx = re.compile(r"""^startserverdemo: recording (?P<name>.+) to (?P<file>.+\.(?:dm_68|urtdemo))$""")
    
    _sql = { 'q1' : "SELECT * FROM `jumpruns` WHERE `client_id` = '%s' AND `mapname` = '%s' AND `way_id` = '%d'",
             'q2' : "SELECT * FROM `jumpruns` WHERE `mapname` = '%s' AND `way_id` = '%d' AND `way_time` < '%d'",
             'q3' : "SELECT * FROM `jumpruns` WHERE `mapname` = '%s' AND `way_time` IN (SELECT MIN(`way_time`) FROM `jumpruns` WHERE `mapname` =  '%s' GROUP BY `way_id`) ORDER BY `way_id` ASC",
             'q4' : "SELECT * FROM `jumpruns` WHERE `client_id` = '%s' AND `mapname` = '%s' ORDER BY `way_id` ASC",
             'q5' : "INSERT INTO `jumpruns` (`client_id`, `mapname`, `way_id`, `way_time`, `time_add`, `time_edit`, `demo`) VALUES ('%s', '%s', '%d', '%d', '%d', '%d', '%s')",
             'q6' : "UPDATE `jumpruns` SET `way_time` = '%d', `time_edit` = '%d', `demo` = '%s' WHERE `client_id` = '%s' AND `mapname` = '%s' AND `way_id` = '%d'", 
             'q7' : "DELETE FROM `jumpruns` WHERE `client_id` = '%s' AND `mapname` = '%s'" }
    
    
    def __init__(self, console, config=None):
        """
        Build the plugin object
        """
        b3.plugin.Plugin.__init__(self, console, config)
        if self.console.gameName != 'iourt42':
            self.critical("unsupported game : %s" % self.console.gameName)
            raise SystemExit(220)
        
      
    def onLoadConfig(self):
        """
        Load plugin configuration
        """
        self.verbose('Loading configuration file...')
        
        try:
            self._demoRecord = self.config.getboolean('settings', 'demorecord')
            self.debug('Loaded automatic demo record: %r' % self._demoRecord)
        except Exception, e:
            self.error('Could not load automatic demo record setting: %s' % e)
            self.debug('Using default value for automatic demo record setting: %r' % self._demoRecord)
        
        try:
            self._minLevelDelete = self.config.getint('settings', 'minleveldelete')
            self.debug('Loaded minimum level delete: %d' % self._minLevelDelete)
        except Exception, e:
            self.error('Could not load minimum level delete setting: %s' % e)
            self.debug('Using default value for minimum level delete setting: %d' % self._minLevelDelete)


    def onStartup(self):
        """
        Initialize plugin settings
        """
        # Get the admin plugin
        self._adminPlugin = self.console.getPlugin('admin')
        if not self._adminPlugin:    
            self.error('Could not find admin plugin')
            return False
        
        # Register our commands
        if 'commands' in self.config.sections():
            for cmd in self.config.options('commands'):
                level = self.config.get('commands', cmd)
                sp = cmd.split('-')
                alias = None
                if len(sp) == 2: 
                    cmd, alias = sp

                func = self.getCmd(cmd)
                if func: 
                    self._adminPlugin.registerCommand(self, cmd, level, func, alias)
        
        # Register the events needed
        self.registerEvent(b3.events.EVT_CLIENT_JUMP_RUN_START)
        self.registerEvent(b3.events.EVT_CLIENT_JUMP_RUN_STOP)
        self.registerEvent(b3.events.EVT_CLIENT_JUMP_RUN_CANCEL)
        self.registerEvent(b3.events.EVT_CLIENT_TEAM_CHANGE)
        self.registerEvent(b3.events.EVT_CLIENT_DISCONNECT)
        self.registerEvent(b3.events.EVT_GAME_ROUND_START)


    # ######################################################################################### #
    # ##################################### HANDLE EVENTS ##################################### #        
    # ######################################################################################### #    
     
     
    def onEvent(self, event):
        """
        Handle intercepted events
        """
        if event.type == b3.events.EVT_CLIENT_JUMP_RUN_START:
            self.onJumpRunStart(event)
        elif event.type == b3.events.EVT_CLIENT_JUMP_RUN_CANCEL:
            self.onJumpRunCancel(event)
        elif event.type == b3.events.EVT_CLIENT_JUMP_RUN_STOP:
            self.onJumpRunStop(event) 
        elif event.type == b3.events.EVT_CLIENT_DISCONNECT:
            self.onDisconnect(event) 
        elif event.type == b3.events.EVT_CLIENT_TEAM_CHANGE:
            self.onTeamChange(event) 
        elif event.type == b3.events.EVT_GAME_ROUND_START:
            self.onRoundStart() 


    # ######################################################################################### #
    # ####################################### FUNCTIONS ####################################### #        
    # ######################################################################################### # 
    
    
    def getCmd(self, cmd):
        cmd = 'cmd_%s' % cmd
        if hasattr(self, cmd):
            func = getattr(self, cmd)
            return func
        return None    
    
    
    def getDateString(self, msec):
        """\
        Return a date string ['Thu, 28 Jun 2001']
        """
        gmtime = time.gmtime(msec)
        return time.strftime("%a, %d %b %Y", gmtime)
        
    
    def getTimeString(self, msec):
        """
        Return a time string given it's value
        expressed in milliseconds [H:mm:ss:ms]
        """
        secs = msec / 1000
        msec -= secs * 1000
        mins = secs / 60
        secs -= mins * 60
        hour = mins / 60
        mins -= hour * 60
        return "%01d:%02d:%02d.%03d" % (hour, mins, secs, msec)
    
    
    def getMapData(self):
        """
        Retrieve map info from UrTJumpers API
        """
        mapData = {}
        self.debug("Contacting http://api.urtjumpers.com to retrieve necessary data...")
        
        try:
        
            jsondata = json.load(urllib2.urlopen('http://api.urtjumpers.com/?key=B3urtjumpersplugin&liste=maps&format=json'))
            for data in jsondata:
                mapData[data['pk3'].lower()] = data
        
        except urllib2.URLError, e:
            self.warning("Could not connect to http://api.urtjumpers.com: %s" % e)
            return { }
            
        self.debug("Retrieved %d maps from http://api.urtjumpers.com" % len(mapData))
        return mapData
    
    
    def getMapsFromListSoundingLike(self, mapname):
        """
        Return a list of maps matching the given search key
        The search is performed on the maplist retrieved from the API
        """
        matches = []
        mapname = mapname.lower()
        
        # Check exact match at first
        if mapname in self._mapData.keys():
            matches.append(mapname)
            return matches
        
        # Check for substring match
        for key in self._mapData.keys():
            if mapname in key:
                matches.append(key)
        
        return matches
        

    def isPersonalRecord(self, event):
        """
        Return True if the client established his new personal record
        on this map and on the given way_id, False otherwise. The function will
        also update values in the database and perform some other operations
        if the client made a new personal record
        """
        client = event.client
        mapname = self.console.game.mapName
        way_id = int(event.data['way_id'])    
        way_time = int(event.data['way_time'])
        demo = client.var(self, 'demoname').value
        
        # Check if the client made his personal record on this map on the specified way_id
        cursor = self.console.storage.query(self._sql['q1'] % (client.id, mapname, way_id))
        if cursor.EOF:
            # No record saved for this client on this map in this way_id. Storing a new tuple in the database for the current run
            self.console.storage.query(self._sql['q5'] % (client.id, mapname, way_id, way_time, self.console.time(), self.console.time(), demo))
            self.verbose("Stored new jumprun for client %s [ mapname : %s | way_id : %d | way_time : %d ]" % (client.id, mapname, way_id, way_time))
            cursor.close()
            return True
        
        r = cursor.getRow()
        if way_time < int(r['way_time']):
            if r['demo'] is not None:
                # Remove previous stored demo
                self.unLinkDemo(r['demo'])
            
            self.console.storage.query(self._sql['q6'] % (way_time, self.console.time(), demo, client.id, mapname, way_id))
            self.verbose("Updated jumprun for client %s [ mapname : %s | way_id : %d | way_time : %d ]" % (client.id, mapname, way_id, way_time))
            cursor.close()
            return True
        
        cursor.close()
        return False
        
    
    def isMapRecord(self, event):
        """
        Return True fs the client established a new absolute record
        on this map and on the given way_id, False otherwise
        """   
        mapname = self.console.game.mapName
        way_id = int(event.data['way_id'])    
        way_time = int(event.data['way_time'])
        
        # Check if the client made an absolute record on this map on the specified way_id
        cursor = self.console.storage.query(self._sql['q2'] % (mapname, way_id, way_time))
        
        if cursor.EOF: 
            cursor.close()
            return True
        
        cursor.close()
        return False
    
        
    def unLinkDemo(self, filename):
        """
        Remove a server side demo file
        """        
        if self.console.game.fs_game is None:
            
            try:
                self.console.game.fs_game = self.console.getCvar('fs_game').getString().rstrip('/')
                self.debug('Retrieved CVAR[fs_game]: %s' % self.console.game.fs_game)
            except Exception, e:
                self.warning('Could not retrieve CVAR[fs_game]: %s' % e)
                self.console.game.fs_game = None
                return
        
        if self.console.game.fs_basepath is None:
        
            try:
                self.console.game.fs_basepath = self.console.getCvar('fs_basepath').getString().rstrip('/')
                self.debug('Retrieved CVAR[fs_basepath]: %s' % self.console.game.fs_game)
            except Exception, e:
                self.warning('Could not retrieve CVAR[fs_basepath]: %s' % e)
                self.console.game.fs_basepath = None
            
        # Construct a possible demo filepath where to search the demo which is going to be deleted
        demopath = self.console.game.fs_basepath + '/' + self.console.game.fs_game + '/' + filename
        
        if not os.path.isfile(demopath):
            self.debug('Could not find demo file at %s' % demopath)
            if self.console.game.fs_homepath is None:
            
                try:
                    self.console.game.fs_homepath = self.console.getCvar('fs_homepath').getString().rstrip('/')
                    self.debug('Retrieved CVAR[fs_homepath]: %s' % self.console.game.fs_game)
                except Exception, e:
                    self.warning('Could not retrieve CVAR[fs_homepath]: %s' % e)
                    self.console.game.fs_homepath = None
                
            # Construct a possible demo filepath where to search the demo which is going to be deleted
            demopath = self.console.game.fs_homepath + '/' + self.console.game.fs_game + '/' + filename
            
        if not os.path.isfile(demopath):
            self.debug('Could not find demo file at %s' % demopath)
            self.error('Could not delete demo file. File not found!')
            return 
            
        try: 
            os.unlink(demopath) 
            self.debug("Deleted file: %s" % demopath)
        except os.error, (errno, errstr):
            # When this happen is mostly a problem related to user permissions
            # Log it as an error so the user will notice and change is configuration
            self.error("Could not delete file: %s | [%d] %s" % (demopath, errno, errstr))
            

    def onJumpRunStart(self, event):
        """
        Handle EVT_CLIENT_JUMP_RUN_START
        """
        client = event.client
        
        if self._demoRecord and client.var(self, 'jumprun').value \
                            and client.var(self, 'demoname').value is not None:
                
            self.console.write('stopserverdemo %s' % (client.cid))
            self.unLinkDemo(client.var(self, 'demoname').value)
        
        client.setvar(self, 'jumprun', True)
        
        # If we are suppose to record a demo of the jumprun
        # start it and store the demo name in the client object
        if self._demoRecord:
            response = self.console.write('startserverdemo %s' % (client.cid))
            match = self._demoRecordRegEx.match(response)
            if match:
                demoname = match.group('file')
                client.setvar(self, 'demoname', demoname)
            else:
                # Something went wrong while retrieving the demo filename
                self.warning("Could not retrieve demo filename for client %s[@%s]: %s" % (client.name, client.id, response))


    def onJumpRunCancel(self, event):
        """
        Handle EVT_CLIENT_JUMP_RUN_CANCEL
        """
        client = event.client
        client.setvar(self, 'jumprun', False)
        
        if self._demoRecord and client.var(self, 'demoname').value is not None:
            # Stop the server side demo of this client
            self.console.write('stopserverdemo %s' % (client.cid))
            self.unLinkDemo(client.var(self, 'demoname').value)


    def onJumpRunStop(self, event):
        """
        Handle EVT_CLIENT_JUMP_RUN_STOP
        """
        client = event.client
        client.setvar(self, 'jumprun', False)

        if self._demoRecord:
            # Stop the server side demo of this client
            self.console.write('stopserverdemo %s' % (client.cid))
        
        if not self.isPersonalRecord(event):
            client.message('^7You can do better! Try again!')
            # If we were recording a server demo, delete the file
            if self._demoRecord and client.var(self, 'demoname').value is not None:
                self.unLinkDemo(client.var(self, 'demoname').value)
                client.setvar(self, 'demoname', None)
            
            return
        
        mapname = self.console.game.mapName
        way_id = int(event.data['way_id'])    
        strtime = self.getTimeString(int(event.data['way_time']))
        
        if self.isMapRecord(event):
            # Informing everyone of the new map record
            self.console.say('^7%s established a new ^1MAP RECORD^7!' % client.name)
            self.console.say('^4%s ^3[way:^7%d^3] ^7| ^2%s' % (mapname, way_id, strtime))
        else:
            # Informing the client of the new personal record
            client.message('^7You established a new ^3PERSONAL RECORD ^7on this map!')
            client.message('^4%s ^3[way:^7%d^3] ^7| ^2%s' % (mapname, way_id, strtime))
        

    def onRoundStart(self):
        """
        Handle EVT_GAME_ROUND_START
        """
        for client in self.console.clients.getList():
            if self._demoRecord and client.var(self, 'jumprun').value \
                                and client.var(self, 'demoname').value is not None:
                
                self.console.write('stopserverdemo %s' % (client.cid))
                self.unLinkDemo(client.var(self, 'demoname').value)
                client.setvar(self, 'jumprun', False)
                
        # Refresh map informations
        self._mapData = self.getMapInfo()
        self._mapsList = self.getMapsList()            
    
    def onDisconnect(self, event):
        """
        Handle EVT_CLIENT_DISCONNECT
        """
        client = event.client
        if self._demoRecord and client.var(self, 'jumprun').value \
                            and client.var(self, 'demoname').value is not None:
            
            # Remove the demo file if we got one since the client
            # has disconnected from the server and we don't need it
            self.unLinkDemo(client.var(self, 'demoname').value)
            
    
    def onTeamChange(self, event):
        """
        Handle EVT_CLIENT_TEAM_CHANGE
        """
        if event.data == b3.TEAM_SPEC:
            
            client = event.client
            if self._demoRecord and client.var(self, 'jumprun').value \
                                and client.var(self, 'demoname').value is not None:
                
                self.console.write('stopserverdemo %s' % (client.cid))
                self.unLinkDemo(client.var(self, 'demoname').value)
                client.setvar(self, 'jumprun', False)


    # ######################################################################################### #
    # ######################################## COMMANDS ####################################### #        
    # ######################################################################################### # 
    
     
    def cmd_jmprecord(self, data, client, cmd=None):
        """\
        [<client>] - Display the record(s) of a client on the current map
        """
        if not data: 
            sclient = client
        else:
            sclient = self._adminPlugin.findClientPrompt(data, client)
            if not sclient: 
                return
    
        mapname = self.console.game.mapName
        cursor = self.console.storage.query(self._sql['q4'] % (sclient.id, mapname))
    
        if cursor.EOF:
            cmd.sayLoudOrPM(client, '^7No record found for %s on map ^4%s' % (sclient.name, mapname))
            cursor.close()
            return
        
        # Print a sort of a list header so players will know what's going on
        cmd.sayLoudOrPM(client, '^7Listing record%s for %s on map ^4%s^7:' % ('s' if cursor.rowcount > 1 else '', 
                                                                              sclient.name, mapname))
        
        while not cursor.EOF:
            r = cursor.getRow()
            sclient = self._adminPlugin.findClientPrompt('@%s' % r['client_id'])
            if not sclient:
                continue
            
            cmd.sayLoudOrPM(client, '^3[^7way:^1%s^3] ^7| ^2%s ^7since ^3%s' % (r['way_id'], 
                                                                                self.getTimeString(int(r['way_time'])), 
                                                                                self.getDateString(int(r['time_edit']))))
            cursor.moveNext()
            
        cursor.close()
        
        
    def cmd_jmpmaprecord(self, data, client, cmd=None):
        """\
        Display the current map record(s)
        """
        mapname = self.console.game.mapName
        cursor = self.console.storage.query(self._sql['q3'] % (mapname, mapname))
        
        if cursor.EOF:
            cmd.sayLoudOrPM(client, '^7No record found for map ^4%s' % mapname)
            cursor.close()
            return
        
        # Print a sort of a list header so players will know what's going on
        cmd.sayLoudOrPM(client, '^7Listing record%s for map ^4%s^7:' % ('s' if cursor.rowcount > 1 else '', mapname))
        
        while not cursor.EOF:
            r = cursor.getRow()
            sclient = self._adminPlugin.findClientPrompt('@%s' % r['client_id'])
            if not sclient:
                continue
            
            cmd.sayLoudOrPM(client, '^7%s ^3[^7way:^1%s^3] ^7| ^2%s' % (sclient.name, r['way_id'], 
                                                                        self.getTimeString(int(r['way_time']))))
            cursor.moveNext()
            
        cursor.close()
    
    
    def cmd_jmpdelrecord(self, data, client, cmd=None):
        """\
        [<client>] - Remove current map client record(s) from the storage
        """
        if not data: 
            sclient = client
        else:
            sclient = self._adminPlugin.findClientPrompt(data, client)
            if not sclient: 
                return
    
        if sclient != client:
            if client.maxLevel < self._minLevelDelete or client.maxLevel < sclient.maxLevel:
                client.message('^7You can\'t delete ^1%s ^7record(s)' % sclient.name)
                return
    
        mapname = self.console.game.mapName
        cursor = self.console.storage.query(self._sql['q4'] % (sclient.id, mapname))
        
        if cursor.EOF:
            client.message('^7No record found for %s on map ^4%s' % (sclient.name, mapname))
            cursor.close()
            return
        
        # Storing number of records
        # for future use (just display)
        num = cursor.rowcount
        
        if self._demoRecord:
            # Removing old demo files if we were supposed to
            # auto record and if the demo has been recorded
            while not cursor.EOF:
                r = cursor.getRow()
                if r['demo'] is not None:
                    self.unLinkDemo(r['demo'])
                cursor.moveNext()
            
        cursor.close()
        
        # Removing database tuples for the given client
        self.console.storage.query(self._sql['q7'] % (sclient.id, mapname))
        self.verbose('Removed %d record%s for %s[@%s] on map %s' % (num, 's' if num > 1 else '', sclient.name, sclient.id, mapname))
        client.message('^7Removed ^1%d ^7record%s for %s on map ^4%s' % (num, 's' if num > 1 else '', sclient.name, mapname))


    def cmd_jmpmapinfo(self, data, client, cmd=None):
        """\
        [<mapname>] Display map specific informations
        """
        if not self._mapData:
            # Fetch info from API
            self._mapData = self.getMapData()
            
        if not self._mapData:
            cmd.sayLoudOrPM(client, 'Could not contact UrTJumpers API')
            return

        if not data:
            # Search info for the current map
            mapname = self.console.game.mapName
        else:
            # Search info for the specified map
            matches = self.getMapsFromListSoundingLike(data) 
            
            if len(matches) == 0:
                client.message('Could not find any map matching ^1%s' % mapname)
                return
            
            if len(matches) > 1:
                client.message('Do you mean: %s?' % ', '.join(matches[:5]))
                return
            
            mapname = matches[0]
        
        mapname = mapname.lower()

        if not self._mapData[mapname]:
            cmd.sayLoudOrPM(client, 'Could not find info for map ^1%s' % mapname) 
            return

        # Fetch informations
        n = self._mapData[mapname]['nom']
        a = self._mapData[mapname]['mapper']
        d = self._mapData[mapname]['mdate']
        j = self._mapData[mapname]['njump']
        t = int(datetime.datetime.strptime(d, '%Y-%m-%d').strftime('%s'))
        l = int(self._mapData[mapname]['level'])
        w = int(self._mapData[mapname]['nway'])
        
        if not a:
            # The author of this map is not stored
            cmd.sayLoudOrPM(client, '^3I don\'t know who created ^7%s' % n)
        else:
            # We know who is the creator of this map
            cmd.sayLoudOrPM(client, '^7%s ^3has been created by ^7%s' % (n, a))
        
        # We always know when the map has been released
        cmd.sayLoudOrPM(client, '^3It has been released on ^7%s' % self.getDateString(t))
        
        if not j:
            # Number of jumps is unknown for this map
            cmd.sayLoudOrPM(client, '^3It\'s composed of ^7%d ^3way%s' % (w, 's' if w > 1 else ' only'))
        else:
            # We know both how many jumps this map has and how many ways
            cmd.sayLoudOrPM(client, '^3It\'s composed of ^7%s ^3jumps and ^7%d ^3way%s' % (j, w, 's' if w > 1 else ''))
            
        if l > 0:
            # Map level is defined
            cmd.sayLoudOrPM(client, '^3Level: ^7%d^3/^7100' % l)

            