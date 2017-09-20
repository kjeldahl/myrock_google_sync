#!/usr/bin/env python
import json

try:
    with open('.myrock_google_sync') as file:
        data = file.read() 
    config = json.loads(data)
except IOError:
    config = {"username": "Google Play username",
             "password": "Google Play password",
             "playlistname": "Playlist name",
             "playlistdescription": "Playlist description" }    
    with open('.myrock_google_sync', 'w') as file:  
        file.write(json.dumps(config, indent=4))

    print "Please fill in the details in the .myrock_google_sync file in the current directory"
    exit(1)

#print 'Loading'
from gmusicapi import Mobileclient
import datetime
import re

try:
    # For Python 3+
    from urllib.request import urlopen
except ImportError:
    # For Python 2
    from urllib2 import urlopen

api = Mobileclient()
print 'Logging in to Google Play'
logged_in = api.login(config['username'], config['password'], Mobileclient.FROM_MAC_ADDRESS)

def findId(title, artist):
    if artist == 'Rammstein': # Rammstein is not available on Google Play only covers
        return None

    results = api.search(title + ', ' + artist)
    for song_hit in results['song_hits']:
        track = song_hit['track']
        # print track
        #if cleanString(track['title']) == cleanString(title) and cleanString(track['albumArtist']) == cleanString(artist):
        # Trust google to find the right version
        return track['storeId'] 

def cleanString(s):
    return re.sub(r"[^\w\s]", '', s.strip().lower())

def findPlaylistId(name):
    
    for playlist in api.get_all_playlists():
        if playlist['name'] == name:
            return playlist['id']
    # None found
    print "Creating playlist"
    playlistId = api.create_playlist(name, config['playlistname'])
    return playlistId

# Returns the first entry in the playlist
def getPlaylistHead(playlistId):
    for playlist in api.get_all_user_playlist_contents():
        if playlist['id'] == playlistId:
            for playlistEntry in playlist['tracks']:
                if playlistEntry['deleted'] == False:
                    return playlistEntry
    return None


def addToPlaylist(title, artist, playlistId):
    trackId = findId(title, artist)
    if trackId != None:
        playlistEntryId = api.add_songs_to_playlist(playlistId, trackId)[0]
        print("Added %(artist)s - %(title)s. (%(playlistEntryId)s)" % locals())
        return playlistEntryId
    else:
        print("Could not find %(artist)s - %(title)s." % locals())
        return None

def getMyRockPlaylist(date):
    print "Fetching playlist from MyRock"
    response = urlopen('https://listenapi.bauerradio.com/api9/eventsdadi/myrock/' + date.strftime('%Y-%m-%d') + '/23:59:59/100') # Date/time and 100 backwards
    data = str(response.read())
    return json.loads(data)

def reorderNewEntries(playlistEntry, origPlayListHead, lastAdded):
    if origPlayListHead is None:
        return lastAdded # List is already in order
    if playlistEntry is not None: # Reorder so new entries are added to the head in the order given by myrock playlist
        try:
            if lastAdded is None:
                #print 'Order front: {}'.format(playlistEntry['id'])
                api.reorder_playlist_entry(playlistEntry, None, origPlayListHead) # Move to front of list
            else:
                #print 'Order: {} - {} - {}'.format(lastAdded['id'], playlistEntry['id'], origPlayListHead['id'])
                api.reorder_playlist_entry(playlistEntry, lastAdded, origPlayListHead) # Move to after previously inserted and before the original head
            return playlistEntry
        except:
            #print 'Reorder failure'
            return lastAdded    
    else:
        return lastAdded

def cleanList(playlistId, maxSize=300):
    playlistEntries = [playlistEntry for playlistEntry in findPlaylistEntries(playlistId) if playlistEntry['deleted'] == False]

    api.remove_entries_from_playlist([playlistEntry['id'] for playlistEntry in playlistEntries[maxSize:]])

def findPlaylistEntries(playlistId):
    return [playlistEntry for playlistEntrys in [playlist['tracks'] for playlist in api.get_all_user_playlist_contents() if playlist['id'] == playlistId] for playlistEntry in playlistEntrys]

def findPlaylistEntry(playlistId, playlistEntryId):
    playlistEntry = [playlistEntry for playlistEntry in findPlaylistEntries(playlistId) if playlistEntry['id'] == playlistEntryId]
    if len(playlistEntry) == 0:
        #print 'Could not find newly added track'
        return None
    else:
        return playlistEntry[0]

if logged_in:
    #print 'Logged in'

    # Used for reordering playlist
    lastAdded = None
    googlePlayMyRockPlaylistId = findPlaylistId(config['playlistname']) 
    origPlayListHead = getPlaylistHead(googlePlayMyRockPlaylistId)
    firstNowPlayingTime = None

    for nowPlayingTrack in getMyRockPlaylist(datetime.datetime.today()):
        if firstNowPlayingTime is None:
            firstNowPlayingTime = nowPlayingTrack['nowPlayingTime']
        if config['lastNowPlayingTime'] == nowPlayingTrack['nowPlayingTime']:
            config['lastNowPlayingTime'] = firstNowPlayingTime
            break
        else:
            playlistEntryId = addToPlaylist(nowPlayingTrack['nowPlayingTrack'].strip(), nowPlayingTrack['nowPlayingArtist'].strip(), googlePlayMyRockPlaylistId)
            if playlistEntryId is not None and origPlayListHead is not None:
                lastAdded = reorderNewEntries(findPlaylistEntry(googlePlayMyRockPlaylistId, playlistEntryId), origPlayListHead, lastAdded)      
    print 'Cleaning up list'
    cleanList(googlePlayMyRockPlaylistId, 300)

    api.logout()
    
    with open('.myrock_google_sync', 'w') as file:  
        file.write(json.dumps(config, indent=4))
else:
    print 'Cannot authorize'

