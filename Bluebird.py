#!/usr/bin/python3.7
import os
import time
import datetime
import re
import cgi
import cgitb; cgitb.enable()  # for troubleshooting
import tweepy #twitter API
import pymongo #MongoDB API
import json
import pprint
from bluebird_settings import *
#email imports-------------------------------
import email, smtplib, ssl
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

#connect to Twitter acccount
auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_KEY, ACCESS_SECRET)
api = tweepy.API(auth, parser=tweepy.parsers.JSONParser())

#connect to MongoDB account
db_connection = pymongo.MongoClient('mongodb+srv://'+DB_USER+':'+DB_PASSWORD+'@'+DB_SERVER)
db = db_connection.BlueBird
captured_accounts = list(db.Captured_Accounts.find())

#other var initializations
Last_Seen_ID_File = 'c:\\inetpub\\wwwroot\\bluebird\\last_seen_id.txt'
Refresh_Wait_File = 'c:\\inetpub\\wwwroot\\bluebird\\refresh_wait.txt'
Rate_Limit_Exceeded = False
me = None
rate_limit_status = None
friends = []
refresh_wait_seconds = 60 #default value

def handle_error(error_, **kwargs):
    result = True #handled error
    message_prefix = kwargs.get('message_prefix', '')
    screen_name = kwargs.get('message_prefix', '<SCREEN NAME NOT SUPPLIED TO MESSAGE HANDLING>')
    user_id = kwargs.get('message_prefix', '<USER ID NOT SUPPLIED TO MESSAGE HANDLING>')
    
    if isinstance(error_, tweepy.RateLimitError):
        print ('<br><logging_warning>'+message_prefix+' I\'ve exceeded my Twitter rate limit</logging_warning>')
        Rate_Limit_Exceeded = True
    else:
        if error_.api_code == 32: #Could not authenticate you
            print ('<br><logging_important>'+message_prefix+'Twitter cound not validate me!</logging_important>')
        elif error_.api_code == 34: #Sorry, that page does not exist. (screen name not found)
            print ('<br><logging_warning>'+message_prefix+'@'+screen_name+' is not a valid Twitter account</logging_warning>')
        elif error_.api_code == 50: #User Id not found.
            print ('<br><logging_warning>'+message_prefix+user_id+' is not a valid Twitter User ID</logging_warning>')    
        elif error_.api_code == 130: #Over capacity
            print ('<br><logging_warning>'+message_prefix+'Twitter is over capacity!</logging_warning>')    
        elif error_.api_code == 131: #Internal error
            print ('<br><logging_warning>'+message_prefix+'Twitter encountered an internal error!</logging_warning>')    
        elif error_.api_code == 136: #You have been blocked from viewing this user's profile.
            print ('<br><logging_warning>'+message_prefix+'@'+screen_name+' has blocked me from reading their tweets</logging_warning>')    
        elif error_.api_code == 187: #Status is a duplicate
            print ('<br><logging_redundant>'+message_prefix+'I already tweeted that exact message at @'+screen_name+'</logging_redundant>')    
        elif error_.api_code == 261: #Application cannot perform write actions. 
            print ('<br><logging_warning>'+message_prefix+'Twitter won\'t allow me to perform write operations</logging_warning>')    
        elif str(error_) == 'Not authorized.': #You're not authorized to view this user's tweets
            print ('<br><logging_warning>'+message_prefix+'I\'m not authorized to view tweets from @'+screen_name+'</logging_warning>')    
        else:
            print ('<br><logging_important>'+message_prefix+'UNHANDLED ERROR!'+'.</logging_important>')
            print ('<br><logging_important>'+str(error_)+'.</logging_important>')
            result = False #unhandled error
    return result

def strip_special_chars(s):
    return re.sub(r'[^\x00-\x7f]',r'', s)

def get_my_profile():
    try:
        me = api.me()
        for friend in api.friends(me.get('id')):
            friends.append(friend)
    except tweepy.TweepError as e:
        handle_error(e, message_prefix = 'Can\'t get my own profile! ')
        return None
    return me

def retrieve_last_seen_id(file_name):
    f_read = open(file_name, 'r')
    last_seen_id = int(f_read.read().strip())
    f_read.close()
    return last_seen_id

def store_last_seen_id(last_seen_id, file_name):
    f_write = open(file_name, 'w')
    f_write.write(str(last_seen_id))
    f_write.close()
    return

def retrieve_refresh_wait(file_name):
    f_read = open(file_name, 'r')
    rws = int(f_read.read().strip())
    f_read.close()
    return rws

def store_refresh_wait(refresh_wait_seconds, file_name):
    f_write = open(file_name, 'w')
    f_write.write(str(refresh_wait_seconds))
    f_write.close()
    return

def clean_screen_name(screen_name):
    #remove a leading @
    return screen_name.lstrip('@').rstrip()

def create_account_doc(twitter_user_object):
    return {"screen_name": twitter_user_object.get('screen_name'),
            "user_id": twitter_user_object.get('id'),
            "created": str(datetime.datetime.now()),
            "last_seen_tweet_id": twitter_user_object.get('status').get('id') if twitter_user_object.get('status') else 1300123456789012345 #an old tweet ID
            #only look for tweets after the latest one
           }

def follow(account):
    account_ = clean_screen_name(account)
    #check if specified account is already being followed
    if (account_ in friends):
        print ('<br><logging_redundant>I\'m already following ' + account + '</logging_redundant>')    
    else:
        #follow specified account
        try:
            api.create_friendship(account_, follow)
            print ('<br><logging_normal>Following ' + account + '</logging_normal>')
        except tweepy.TweepError as e:
            handle_error(e, message_prefix = 'Can\'t follow @'+account_+'. ', screen_name='@'+account_)            
    return

def unfollow(account):
    account_ = clean_screen_name(account)
    #check if specified account is already being followed
    if (account_ in friends):
        #unfollow this account
        try:
            api.destroy_friendship(account_)
            print ('<br><logging_normal>Unfollowing ' + account + '</logging_normal>')
        except tweepy.TweepError as e:
            handle_error(e, message_prefix = 'Can\'t unfollow @'+account_+'. ', screen_name='@'+account_)            
    else:
        print ('<br><logging_redundant>I wasn\'t following @' + account_ + '</logging_redundant>')    
    return

def add_captured_account(account):
    account_ = clean_screen_name(account)
    #check if specified account is already being captured
    result = next((item for item in captured_accounts if item['screen_name'] == account_), None)
    
    if result == None:
        #check if account exists
        try:
            api_account = api.get_user(account_)
            capturee = create_account_doc(api_account)
            db.Captured_Accounts.insert_one(capturee)
            captured_accounts.append(capturee)
            print('<br><logging_normal>Began capturing tweets from '+account+'</logging_normal>')
        except tweepy.TweepError as e:
            handle_error(e, message_prefix = 'Can\'t capture tweets from @'+account_+'. ', screen_name='@'+account_)            
    else:
        print('<br><logging_redundant>I was already capturing tweets from '+account+'</logging_redundant>')
    return

def gather_tweets_from_captured_accounts():
    #gather tweet content from captured accounts
    captured_tweet_count = 0
    captured_accounts = list(db.Captured_Accounts.find()) #reload!
    for account in captured_accounts:
        #get the unseen tweets from the account
        try:
            tweet_timeline = api.user_timeline(
                user_id = account.get('user_id'),
                since_id = account.get('last_seen_tweet_id'), tweet_mode='extended')
            #store gathered tweets, if any
            if len(tweet_timeline) > 0:
                db.Captured_Tweets.insert_many(tweet_timeline)
                #keep a running total
                captured_tweet_count += len(tweet_timeline)
                #update last seen tweet id for the account
                db.Captured_Accounts.update_one({'screen_name': account.get('screen_name')}, {'$set': { 'last_seen_tweet_id': tweet_timeline[0].get('id') }})
        except tweepy.TweepError as e:
            handle_error(e, message_prefix = 'Can\'t gather more tweets! ', screen_name='@'+account.get('screen_name'), user_id = account.get('user_id'))
            break
    return captured_tweet_count

def discard_stale_tweets():
    #keep tweets within the last 25,000,000,000,000 (yes that's 25 trillion)
    latest_tweet = db.Captured_Tweets.find_one({}, sort=[("id", pymongo.DESCENDING)])
    best_after_tweet_id = latest_tweet.get('id') - 25000000000000
    result = db.Captured_Tweets.delete_many({ 'id':{ '$lt': best_after_tweet_id } })
    return result.deleted_count

def keep_deleted_tweets():
    deleted_tweet_count = 0        
    #re-find each captured tweet (up to a certain age), by age
    captured_tweets = db.Captured_Tweets.find({}, sort=[("id", pymongo.DESCENDING)])
    for tweet in captured_tweets:
        try:
            api.get_status(id=tweet.get('id'))
        except tweepy.TweepError as e:
            if e.api_code == 144: #captured tweet was not found   
                db.Deleted_Tweets.insert_one(tweet) #save tweet to "Deleted" pile
                db.Captured_Tweets.delete_one({'id': tweet.get('id')}) #don't check for it again
                deleted_tweet_count += 1
            else:
                handle_error(e, message_prefix = 'Can\'t check for deleted tweets! ')
                break
    return deleted_tweet_count

def process_new_mentions():
    last_seen_id = retrieve_last_seen_id(Last_Seen_ID_File)
    # NOTE: We need to use tweet_mode='extended' below to show all full
    # tweets (with full_text). Without it, long tweets would be cut off.
    mentions = api.mentions_timeline(
                        last_seen_id,
                        tweet_mode='extended')

    #is anyone talking to me?
    if len(mentions) == 0:
        print('<p><logging_normal>I didn\'t find any new commands.</logging_normal>')
    
    for mention in reversed(mentions):
        mention_handled = False
        global refresh_wait_seconds

        #show the command being processed
        print('<p><logging_normal>Processing command (<mention_id_normal>'+mention.get('id_str')+'</mention_id_normal>) from @'+mention.get('user').get('screen_name')+': </logging_normal><mention_normal>'+mention.get('full_text')+'</mention_normal>')

        #turn the mention tweet's text into a list, delimited by spaces
        mention_parts = list(mention.get('full_text').split(' '))
        
        #get rid of empty parts (these were extra spaces in the original mention)
        mention_parts = list(filter(None, mention_parts))
        
       
        #@[bot account] az5
        if mention_parts[1].lower() == 'az5':
            #clear all data
            db.Captured_Accounts.drop()
            db.Captured_Tweets.drop()
            db.Deleted_Tweets.drop()
            captured_accounts.clear()
            print('<br><logging_important>ALL DATA DROPPED!</logging_important>')
            mention_handled = True

        #@[bot account] capture @[target account]
        if mention_parts[1].lower() == 'capture':
            #add specified account to the list of captured accounts
            if len(mention_parts) >= 3:
                add_captured_account(mention_parts[2])
            mention_handled = True
            
        #@[bot account] uncapture @[target account]
        if mention_parts[1].lower() == 'uncapture':
            #remove specified account from the list of captured accounts
            captured_account_doc = db.Captured_Accounts.find_one({'screen_name':clean_screen_name(mention_parts[2])})
            if captured_account_doc == None:
                print('<br><logging_redundant>I wasn\'t capturing tweets from @'+clean_screen_name(mention_parts[2])+'.</logging_redundant>')
            else:
                db.Captured_Accounts.delete_one(captured_account_doc)
                captured_accounts = list(db.Captured_Accounts.find()) #reload!
                print('<br><logging_normal>Stopped capturing tweets from @'+clean_screen_name(mention_parts[2])+'</logging_normal>')
            mention_handled = True
        
        #@[bot account] follow @[target account]
        if mention_parts[1].lower() == 'follow':
            #follow the specified account
            follow(mention_parts[2])
            #reply to mentioner
            try:
                if RESPOND_TO_MENTIONS == True:
                    api.update_status('@' + mention.get('user').get('screen_name') + ' ' +
                        'I\'m now following ' + mention_parts[2], in_reply_to_status_id=mention.get('id'), auto_populate_reply_metadata=True)
            except tweepy.TweepError as e:
                handle_error(e, message_prefix = 'Can\'t reply to @'+mention.get('user').get('screen_name')+'. ', screen_name = mention.get('user').get('screen_name'))
            mention_handled = True

        #@[bot account] unfollow @[target account]
        if mention_parts[1].lower() == 'unfollow':
            #unfollow the specified account
            unfollow(mention_parts[2])
            #reply to mentioner
            try:
                if RESPOND_TO_MENTIONS == True:
                    api.update_status('@' + mention.get('user').get('screen_name') + ' ' +
                        'I\'m no longer following ' + mention_parts[2], in_reply_to_status_id=mention.get('id'), auto_populate_reply_metadata=True)
            except tweepy.TweepError as e:
                handle_error(e, message_prefix = 'Can\'t notify @'+mention.get('user').get('screen_name')+'. ', screen_name = mention.get('user').get('screen_name'))
            mention_handled = True

        #@[bot account] refresh [number of seconds]
        if mention_parts[1].lower() == 'refresh':
            #set the refresh rate to the specified number of seconds
            try:
                refresh_wait_seconds = int(mention_parts[2])
                store_refresh_wait(refresh_wait_seconds, Refresh_Wait_File)
            except:
                print ('<br><logging_warning>The refresh rate you specified was invalid! Expected format: refresh ## (ie. refresh 45)</logging_warning>')
            mention_handled = True

        #@[bot account] deleted [email address]
        if mention_parts[1].lower() == 'deleted':
            #send all the deleted tweets to the specified email address
            message = MIMEMultipart()
            message["From"] = SENDER_EMAIL
            message["To"] = SENDER_EMAIL
            message["Subject"] = 'Deleted Tweets from '+datetime.datetime.now().strftime("%A, %b %d, %Y %I:%M%p")
            message["Bcc"] = mention_parts[2]
            try:
                body = '<html><body>Here are the deleted tweets I\'ve found so far:'
                deleted_tweets = db.Deleted_Tweets.find({}, sort=[("id", pymongo.DESCENDING)])
                for tweet in deleted_tweets:
                    body += '<p><b>@'+tweet.get('user').get('screen_name')+'</b>'
                    body += '<br>'+strip_special_chars(tweet.get('full_text'))
                    body += '<br><i><style="color:#606060;font-size:75%">'+tweet.get('created_at')+'</style></i>'
                body += '</body></html>'
                print(body)
                message.attach(MIMEText(body, 'html'))
                content = message.as_string()
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                    server.login(SENDER_EMAIL, SENDER_EMAIL_PASSWORD)
                    server.sendmail(SENDER_EMAIL, mention_parts[2], content)
                print ('<br><logging_normal>I sent the deleted tweets to '+mention_parts[2]+'</logging_normal>')
            except tweepy.TweepError as e:
                handle_error(e, message_prefix = 'Can\'t email the deleted tweets to ' + mention_parts[2] + '! ', screen_name = mention.get('user').get('screen_name'))
            mention_handled = True
            
        #@[bot account] tweet [message]
        if mention_parts[1].lower() == 'tweet':
            #tweet the specified message to the specified account
            #combine the tweet text parts into a single string, preceeded by a space
            tweet_text = ' '.join(map(str, mention_parts[2:]))
            print ('<br>Sending tweet: '+tweet_text)
            try:
                api.update_status(tweet_text)
                print ('<br><logging_normal>Tweet sent!</logging_normal>')
            except tweepy.TweepError as e:
                handle_error(e, message_prefix = 'Can\'t send Tweet!', screen_name = mention.get('user').get('screen_name'))
            mention_handled = True

        #@[bot account] DM @[target account] [message]
        if mention_parts[1].lower() == 'DM':
            #DM the specified message to the specified account
            #combine the tweet text parts into a single string, preceeded by a space
            try:
                dm_text = ' '.join(map(str, mention_parts[3:]))
                print ('<br>Sending DM to '+mention_parts[2]+': '+dm_text)
            except:
                print ('<br><logging_warning>DM doesn\'t specify a message!</logging_warning>')
            try:
                dm_target = api.get_user(clean_screen_name(mention_parts[2]))
                api.send_direct_message(dm_target.get('user_id'), dm_text)
                print ('<br><logging_normal>DM sent!</logging_normal>')
            except tweepy.TweepError as e:
                handle_error(e, message_prefix = 'Can\'t DM @'+dm_target.get('screen_name')+'. ', screen_name = dm_target.get('screen_name'))
            mention_handled = True
        
        if not mention_handled:
            #reply to mentioner:
            replies_part1 = [
                'I don''t understand',
                'that doesn''t make sense',
                'say what?',
                'huh?',
                'what does that mean?',
                'are you feeling ok?',
                'I think you''ve been hacked'
                ]
            replies_part2 = [
                'Could you elaborate?',
                'Please explain',
                'Sorry, I\'m dumb',
                '(puts on thinking cap)',
                '#IAmDumb',
                '#IDon\'tGetIt',
                '#mystery',
                '#enigma',
                '#RiddleMeThis',
                '#Ain\'tNobodyGotTimeForThat'
                ]
            replies_part3 = [
                '#truth',
                '#pontificate',
                '#SpillIt',
                '#ForRealsDawg',
                '#GiveItToMeRaw',
                '#OnTheDownLow',
                '#GetReal',
                '#ForShizzle'
                ]
            print('<br><logging_warning>Unknown command: '+mention.get('full_text')+'</logging_warning>')
            #reply to mentioner
            try:
                if RESPOND_TO_MENTIONS:
                    api.update_status(
                        '@' + mention.get('user').get('screen_name') + ' ' +
                        replies_part1[
                            random.randint(0, 6)]+' '+
                            replies_part2[random.randint(0, 9)]+' '+
                            replies_part3[random.randint(0, 7)],
                        in_reply_to_status_id=mention.get('id'),
                        auto_populate_reply_metadata=True)
            except tweepy.TweepError as e:
                handle_error(e, message_prefix = 'Can\'t reply to @'+mention.get('user').get('screen_name')+'. ')

        last_seen_id = mention.get('id')
        store_last_seen_id(last_seen_id, Last_Seen_ID_File)
    return

#action delegation
def perform_actions():
    global refresh_wait_seconds
    global rate_limit_status
    me = get_my_profile()
    if (me == None) or (rate_limit_status == None):
        return
    refresh_wait_seconds = retrieve_refresh_wait(Refresh_Wait_File)
    if Rate_Limit_Exceeded:
        print('<p><logging_normal>Hello, I woke up at '+str(datetime.datetime.now())+'</logging_normal>')
        print('<p><logging_important>My rate limit on twitter was exceeded, so I can\'t do any work!</logging_important>')
    else:
        print('<p><logging_normal>Hello, I am <my_screen_name>@'+me.get('screen_name')+'</my_screen_name> and I woke up at '+str(datetime.datetime.now())+'</logging_normal>')
        print('<p><logging_normal>I\'m currently capturing tweets from '+str(db.Captured_Accounts.count_documents({}))+' account(s).</logging_normal>')
        capture_count = gather_tweets_from_captured_accounts()
        if capture_count >= 1:
            print('<p><logging_normal>I captured '+str(capture_count)+' new tweet(s).</logging_normal>')
        else:
            print('<p><logging_normal>I didn\'t find any new tweets from the accounts I\'m watdhing.</logging_normal>')
        process_new_mentions()
        dicard_count = discard_stale_tweets()
        if dicard_count >= 1:
            print('<p><logging_normal>I removed '+str(dicard_count)+' stale captured tweet(s).</logging_normal>')
        else:
            print('<p><logging_normal>All my captured tweets are still fresh.</logging_normal>')
        deleted_count = keep_deleted_tweets()
        if deleted_count >= 1:
            print('<p><logging_important>I FOUND '+str(deleted_count)+' DELETED TWEET(S)!</logging_important>')
        else:
            print('<p><logging_normal>I didn\'t find any more deleted tweets.</logging_normal>')
    print('<p><logging_normal>I went back to sleep for '+str(refresh_wait_seconds)+' seconds at '+str(datetime.datetime.now())+'</logging_normal>')

print ('Content-Type: text/html')
print ('\n')
print ('<html>')
print ('<head><title>Deleted Tweet Capture Bot</title>')
print ('<link rel = "stylesheet" type = "text/css" href = "bluebird.css" />')
print ('</head>')
print ('<body>')
rate_limit_status = api.rate_limit_status()
print ('<table>')
print ('<thead><tr><th>Resource</th><th>Hits Remaining</th></tr></thead>')
print ('<tbody>')
print ('<tr><td>application/rate_limit_status</td><td>'+str(rate_limit_status.get('resources').get('application').get('/application/rate_limit_status').get('remaining'))+'</td></tr>')
print ('<tr><td>user_timeline</td><td>'+str(rate_limit_status.get('resources').get('statuses').get('/statuses/show/:id').get("remaining"))+'</td></tr>')
print ('<tr><td>mentions_timeline</td><td>'+str(rate_limit_status.get('resources').get('statuses').get('/statuses/user_timeline').get("remaining"))+'</td></tr>')
print ('<tr><td>friends/list</td><td>'+str(rate_limit_status.get('resources').get('friends').get('/friends/list').get("remaining"))+'</td></tr>')
print ('<tr><td>account/verify_credentials</td><td>'+str(rate_limit_status.get('resources').get('account').get('/account/verify_credentials').get("remaining"))+'</td></tr>')
print ('</tbody>')
print ('</table>')
perform_actions()
print ('<SCRIPT>')
print ('<!--')
print ('setTimeout(() => window.location.reload(), '+str(refresh_wait_seconds)+'000);')
print ('-->')
print ('</SCRIPT>')
print ('</body></html>')
