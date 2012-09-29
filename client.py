import logging
import hashlib
import time
import os
import lightdht
import torrent
import json
import urllib
import urllib2
import traceback
import bencode

API_URL = "http://localhost:8080/mapi/";
API_PASS = "test"

# Enable logging:
lightdht.logger.setLevel(logging.WARNING)	 
formatter = logging.Formatter("[%(levelname)s@%(created)s] %(message)s")
stdout_handler = logging.StreamHandler()
stdout_handler.setFormatter(formatter)
lightdht.logger.addHandler(stdout_handler)

# Create a DHT node.
dht = lightdht.DHT(port=8000) 

#Running torrents that are downloading metadata
manager = torrent.TorrentManager(dht, 8000, None)
found_torrents = set()

#Maximal simultanous jobs
MAX_JOBS = 20

def addHash(info_hash):
	if len(info_hash) == 20:
		found_torrents.add(info_hash)

def makeRequest(method, body = None):
	try:
		data = {'method':method, 'password':API_PASS}
		if body != None:
			body = bencode.bencode(body).encode("base64")
			data['body'] = body
		data = urllib.urlencode(data)
		req = urllib2.Request(API_URL,data)
		response = urllib2.urlopen(req).read()
		return bencode.bdecode(response.decode("base64"))
	except urllib2.HTTPError, e:
		print "Error while making requests: "+str(e)
	return None

def sendFound():
	if len(found_torrents) == 0:
		return
	to_send = list()
	while len(found_torrents) != 0:
		to_send.append(found_torrents.pop())
	print("Sending %d info_hashes to server" % len(to_send))
	makeRequest('put_hashes',to_send)

def processFinished(info_hash, peers, data):
	req = {'info_hash':info_hash, 'peers':peers}
	if data != None:
		req['metadata'] = data
	print "Sending info of %s" % info_hash.encode("hex")
	makeRequest('update',req)		

def get_work():
	return makeRequest('get_work')

# handler
def myhandler(rec, c):
	try:
		if "a" in rec:
			a = rec["a"]
			if "info_hash" in a:
				info_hash = a["info_hash"]
				addHash(info_hash)

	finally:
		# always ALWAYS pass it off to the real handler
		dht.default_handler(rec,c) 

dht.handler = myhandler
dht.active_discovery = True 
dht.self_find_delay = 30

# Start it!
with dht:
	print "Started"
	# Go to sleep and let the DHT service requests.
	while True:
		sendFound()
		ret = manager.fetchAndRemove()
		if ret != None:
			info_hash, peers, data = ret
			processFinished(info_hash, peers, data)
		if manager.count() < MAX_JOBS:
			work =  get_work()
			if work['type'] == 'download_metadata':
				manager.addTorrent(work['info_hash'])
			elif work['type'] == 'check_peers':
				manager.addTorrent(work['info_hash'], metadata = False)
		time.sleep(10)	
