# -*- coding: utf-8 -*-
"""
Created on Fri Sep 02 11:39:00 2016

@author: jiachen.yang@gatech.edu
"""

import tweepy
import time
import urllib2
import re
import datetime

class rlbot:
    
    def __init__(self, name, keyfile, duration=1, period=30):
        """
        Arguments:
        1. name - name of bot
        2. keyfile - path to file containing consumer and access tokens
        3. duration - length of time to run the bot (unit: minutes)
        4. period - sampling period (unit: seconds)        
        """
        self.name = name
        self.keyfile = keyfile
        self.duration = duration
        self.period = period
        self.margin = 5 # when waiting for limits to reset, give 5sec margin        
        
        self.tstart = time.time()

        # A local copy of the number of remaining allowed queries that
        # Twitter holds on their server,
        # and the purpose of maintaining this local copy is to avoid calling
        # api.rate_limit_status() before every call, because rate_limit_status()
        # is limited to 180calls/15min
        # The main bot program will sync this up with Twitter's record
        # every 15 minutes
        self.remaining = {'followers':15, 'timeline':900, 'status_lookup':900,
                          'search':180,
                          'retweets':75, 'retweets_of_me':75, 'friends':15,
                          'user':900, 'user_lookup':900, 'update':25,
                          'trends_place':75}
        
        # Initialize connection to API
        self.api = self.activate()
        # Reset API request limits
        self.update_limits()
        # List of follower id_str
        self.followers = []
        self.num_follower = 0
        self.update_followers()
        # Set of id_str of people who are tracked by this bot
        self.tracking = set()

        # User object
        self.user = self.api.get_user(self.name)
        # User ID of bot
        self.id_str = self.user.id_str
        # Reset API request limits again, after the previous two commands
        self.update_limits()
        
        
    def activate(self, verbose=0):
        """
        Instantiates the Tweepy API object using the consumer and access keys        
        
        Returns: Tweepy api object
        """
        
        f = open(self.keyfile, 'r')
        lines = f.readlines()
        f.close()
        
        consumer_key = lines[0].strip()
        consumer_secret = lines[1].strip()
        access_token = lines[2].strip()
        access_token_secret = lines[3].strip()
        
        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        auth.set_access_token(access_token, access_token_secret)
        
        api = tweepy.API(auth)
        
        if verbose:
            print "Bot %s has activated" % self.name
    
        return api
    
    
    def get_limits(self, limits, choice=""):
        """
        Argument:
        1. limits - the dictionary returned by api.rate_limit_status()
        2. choice - type of resource to look up        
        
        Organization:
        limits  rate_limit_context
                resources   
                            help, moments, tweet_prompts, live_pipeline, friendships,
                            statuses, feedback, drafts, contacts, media,
                            business_experience, geo, application, collections, followers,
                            mutes, saved_searches, blocks, users, search,
                            auth, lists, favorites, device, friends,
                            account, live_video_stream, trends, direct_messages
        
        """
#        limits = self.api.rate_limit_status()
        
        followers = limits['resources']['followers']
        friends = limits['resources']['friends']
        users = limits['resources']['users']
        statuses = limits['resources']['statuses']
        search = limits['resources']['search']
        trends = limits['resources']['trends']

        if choice == "followers":
            return followers['/followers/ids']['remaining'] # lim 15/15min
        elif choice == "friends":
            return friends['/friends/ids']['remaining'] # lim 15/15min
        elif choice == "user":
            return users['/users/show/:id']['remaining'] # lim 900/15min
        elif choice == "user_lookup":
            return users['/users/lookup']['remaining'] # lim 900/15min
        elif choice == "timeline":
            return statuses['/statuses/user_timeline']['remaining'] # lim 900/15min
        elif choice == "status_lookup":
            return statuses['/statuses/lookup']['remaining'] # lim 900/15min
        elif choice == "search":
            return search['/search/tweets']['remaining'] # lim 180/15min
        elif choice == "retweets":
            return statuses['/statuses/retweets/:id']['remaining'] # 75/15min
        elif choice == "retweets_of_me":
            return statuses['/statuses/retweets_of_me']['remaining'] # 75/15min
        elif choice == "trends_place":
            return trends['/trends/place']['remaining'] # 75/15min
        else:
            return 0


    def get_resettime(self, limits, choice=""):
        """
        Argument:
        1. limits - the dictionary returned by api.rate_limit_status()
        2. choice - type of resource to look up        
        
        Organization:
        limits  rate_limit_context
                resources   
                            help, moments, tweet_prompts, live_pipeline, friendships,
                            statuses, feedback, drafts, contacts, media,
                            business_experience, geo, application, collections, followers,
                            mutes, saved_searches, blocks, users, search,
                            auth, lists, favorites, device, friends,
                            account, live_video_stream, trends, direct_messages
        
        """
#        limits = self.api.rate_limit_status()
        
        followers = limits['resources']['followers']
        friends = limits['resources']['friends']
        users = limits['resources']['users']
        statuses = limits['resources']['statuses']
        search = limits['resources']['search']    
        
        if choice == "followers":
            return followers['/followers/ids']['reset'] # lim 15/15min
        elif choice == "friends":
            return friends['/friends/ids']['reset'] # lim 15/15min
        elif choice == "user":
            return users['/users/show/:id']['reset'] # lim 900/15min
        elif choice == "user_lookup":
            return users['/users/lookup']['reset'] # lim 900/15min
        elif choice == "timeline":
            return statuses['/statuses/user_timeline']['reset'] # lim 900/15min
        elif choice == "status_lookup":
            return statuses['/statuses/lookup']['reset'] # lim 900/15min
        elif choice == "search":
            return search['/search/tweets']['reset'] # lim 180/15min
        elif choice == "retweets":
            return statuses['/statuses/retweets/:id']['reset'] # 75/15min
        elif choice == "retweets_of_me":
            return statuses['/statuses/retweets_of_me']['reset'] # 75/15min
        elif choice == "trends_place":
            return trends['/trends/place']['reset'] # 75/15min
        else:
            return (time.time() + 5*60)

    def update_limits(self):
        """
        Reset the self.remaining dictionary to values retrieved from the
        Tweeter API
        
        """
        limits = self.api.rate_limit_status()        
        
        self.remaining['followers'] = self.get_limits(limits, 'followers')
        self.remaining['friends'] = self.get_limits(limits, 'friends')
        self.remaining['timeline'] = self.get_limits(limits, 'timeline')
        self.remaining['status_lookup'] = self.get_limits(limits, 'status_lookup')
        self.remaining['search'] = self.get_limits(limits, 'search')
        self.remaining['retweets'] = self.get_limits(limits, 'retweets')
        self.remaining['retweets_of_me'] = self.get_limits(limits, 'retweets_of_me')
        self.remaining['user'] = self.get_limits(limits, 'user')
        self.remaining['user_lookup'] = self.get_limits(limits, 'user_lookup')
        self.remaining['trends_place'] = self.get_limits(limits, 'trends_place')
        self.remaining['update'] = 25


    def wait_limit_reset(self, choice=""):
        """
        Entered this function only because self.remaining[choice] == 0
        Gets the time when the chosen API limit will reset, then sleeps
        until that time, plus some margin
        """
        done = 0
        while done == 0:
            try:
                # In case self.remaining[choice] and actual limits are not synced
                limits = self.api.rate_limit_status()
                limit_actual = self.get_limits(limits, choice)
                if limit_actual != 0:
                    self.remaining[choice] = limit_actual
                else:
                    current_time = time.time()
                    reset_time = self.get_resettime(limits, choice)
                    if ( reset_time > current_time ):
                        t_delta = reset_time - current_time + self.margin
                        print "%s wait %d seconds for %s limit to reset" % \
                            (self.name, t_delta, choice)
                        time.sleep(t_delta)
                        self.update_limits()
                return
            except tweepy.TweepError:
                # Somehow api.rate_limit_status() itself reached the rate limit, so wait
                # and try again
                time.sleep(60)


    def get_users(self, list_uid=[]):
        """
        Argument:
        1. list_uid - list of userids
        
        Returns:
        1. list of user objects
        """
        list_users = []
        done = 0
        while done == 0:
            if (self.remaining['user_lookup'] != 0):
                try:
                    list_users = self.api.lookup_users(user_ids=list_uid)
                    self.remaining['user_lookup'] -= 1
                    done = 1
                except tweepy.RateLimitError:
                    print "%s get_users() rate limit error" % self.name
                    self.wait_limit_reset('user_lookup')
                except tweepy.TweepError:
                    return list_users
            else:
                self.wait_limit_reset('user_lookup')

        return list_users


    def get_followers(self, userid=None, verbose=0):
        """
        Gets all followers of the specified user and returns list of IDs
        
        Argument:
        1. userid - user ID or screen_name (if None, then user is this bot)
                
        Returns: 
        1. list of follower IDs (max 5000)
        """

        followers = []
        done = 0
        
        while done == 0:
            if ( self.remaining['followers'] != 0 ):
                try:            
                    followers = self.api.followers_ids(userid, stringify_ids=True)
                    self.remaining['followers'] -= 1
                    done = 1
                except tweepy.RateLimitError:
                    print "%s get_followers() rate limit error" % self.name
                    self.wait_limit_reset('followers')
                except tweepy.TweepError:
                    return followers
            else:
                self.wait_limit_reset('followers')
            
        return followers
            

    def get_followers_cursored(self, user=None, cursor=-1, stringify=False):
        """
        returns list_of_follower_IDs, next_cursor
        """
        followers = []
        done = 0
        while done == 0:
            if ( self.remaining['followers'] != 0 ):
                try:
                    returned = self.api.followers_ids(user, cursor=cursor, stringify_ids=stringify)
                    followers = returned[0]
                    next_cursor = returned[1][1]
                    self.remaining['followers'] -= 1
                    done = 1
                except tweepy.RateLimitError:
                    print "%s get_followers_cursored() rate limite error" % self.name
                    self.wait_limit_reset('followers')
                except tweepy.TweepError:
                    return followers
            else:
                self.wait_limit_reset('followers')

        return followers, next_cursor


    def update_followers(self):
        # self.followers = self.get_followers()
        done = 0
        while done == 0:
            if ( self.remaining['user'] != 0 ):
                try:
                    self.user = self.api.get_user(self.name)
                    self.remaining['user'] -= 1
                    self.num_followers = self.user.followers_count
                except tweepy.TweepError:
                    pass
                done = 1
            else:
                self.wait_limit_reset('user')

            
    def get_friends(self, userid=None, verbose=0):
        """
        Gets all people being followed by the specified user, returns list of IDs
        
        Argument:
        1. userid - user ID or screen_name (if None, then user is this bot)
        
        Returns: 
        1. list of friend_id
        """
    
        friends = []
        done = 0
        
        while done == 0:
            if ( self.remaining['friends'] != 0 ):
                try:            
                    friends = self.api.friends_ids(userid, stringify_ids=True)
                    self.remaining['friends'] -= 1
                    done = 1
                except tweepy.RateLimitError:
                    print "%s get_friends() rate limit error" % self.name
                    self.wait_limit_reset('friends')
                    continue
                except tweepy.TweepError:
                    return friends
            else:
                self.wait_limit_reset('friends')
    
        return friends
        
        
    def update_tracking(self, list_ids):
        """
        Updates self.tracking
        
        Argument:
        1. list_ids - list of id_str of accounts whose followers should be tracked
        """
        for user_id_str in list_ids:
            list_follower = self.get_followers(user_id_str)
            for follower in list_follower:
                self.tracking.add(follower)


    def get_tweets(self, list_id):
        """
        Given an ordered list of tweet IDs, returns ordered list of 
        tweet objects
        
        Argument:
        1. list_id - ordered list of tweet IDs
        Returns: 
        1. list of tweet objects
                        
        Note
        1. api.statuses_lookup takes in a list of max length 100        
        """
        list_tweets = []
        idx_start = 0
        total = len(list_id)
        idx_end = min(idx_start+100, total)
        while idx_start != total:
            if ( self.remaining['status_lookup'] != 0 ):
                try:
                    tweet_list = self.api.statuses_lookup(list_id[idx_start:idx_end])
                    self.remaining['status_lookup'] -= 1
                    # Store into the final output list
                    list_tweets = list_tweets + tweet_list
                    # Update list boundaries
                    idx_start = idx_end
                    idx_end = min(idx_start+100, total)
                except tweepy.RateLimitError:
                    print "%s get_tweets() rate limit error" % self.name
                    self.wait_limit_reset('status_lookup')
                except tweepy.TweepError:
                    return list_tweets
            else:
                self.wait_limit_reset('status_lookup')
                
        return list_tweets

        
    def get_num_like_retweet(self, list_id):
        """
        Given an ordered list of tweet IDs, returns ordered list of 
        number of likes and ordered list of number of retweets
        
        Argument:
        1. list_id - ordered list of tweet IDs
        
        Returns: 
        1. list of number of likes
        2. list of number of retweets         
                        
        Note
        1. api.statuses_lookup takes in a list of max length 100
        """
        list_like = []
        list_retweet = []
        
        idx_start = 0
        total = len(list_id)
        idx_end = min(idx_start+100, total)
        while idx_start != total:
            if ( self.remaining['status_lookup'] != 0 ):
                try:
                    tweet_list = self.api.statuses_lookup(list_id[idx_start:idx_end])
                    self.remaining['status_lookup'] -= 1
                    
                    # Extract the number of likes and retweets for each tweet
                    like_list = [tweet.favorite_count for tweet in tweet_list]
                    retweet_list = [tweet.retweet_count for tweet in tweet_list]
                    
                    # Store into the final output list
                    list_like.extend(like_list)
                    list_retweet.extend(retweet_list)
                    
                    # Update list boundaries
                    idx_start = idx_end
                    idx_end = min(idx_start+100, total)
                except tweepy.RateLimitError:
                    print "%s get_num_like_retweet() rate limit error" % self.name
                    self.wait_limit_reset('status_lookup')
                except tweepy.TweepError:
                    return list_like, list_retweet
            else:
                self.wait_limit_reset('status_lookup')
                
        return list_like, list_retweet

        
    def get_timeline_since(self, userid, since, verbose=0):
        """
        Returns all tweets posted since the tweet with id=since        
        
        Arguments:
        1. userid - user ID or scree_name (if none, then user is this bot)
        2. since - id_str of the tweet such that all tweets more recent than this
                    will be returned, not including this tweet
        
        Returns:
        1. list of TWEET objects, ordered from most recent to oldest     
        """        
        tweet_list = []

        found = 0
        done = 0
        # initial acquisition
        while done == 0:
            if ( self.remaining['timeline'] != 0 ):
                try:
                    tweets = self.api.user_timeline(userid, count=200)
                    self.remaining['timeline'] -= 1
                    if len(tweets) == 0:
                        return tweet_list
                    else:
                        tweet_list.extend(tweets)
                        for idx in range(0, len(tweet_list)):
                            # If found the tweet with id_str = since, return the
                            # slice with higher indices
                            if tweet_list[idx].id_str == since:
                                found = 1
                                return tweet_list[:idx]
                        # starting point of next acquisition
                        last = tweet_list[-1].id - 1
                        done = 1
                except tweepy.RateLimitError:
                    print "%s get_timeline_since() rate limit error" % self.name
                    self.wait_limit_reset('timeline')
                except tweepy.TweepError:
                    return tweet_list
            else:
                self.wait_limit_reset('timeline')

        # While not found, search further back in time starting from last
        while found == 0 and len(tweets) != 0:
            done = 0
            while done == 0:
                if ( self.remaining['timeline'] != 0 ):
                    try:
                        tweets = self.api.user_timeline(userid, count=200, 
                                                            max_id=last)
                        self.remaining['timeline'] -= 1
                        if len(tweets) == 0: # no more to find, so return empty list
                            return []
                        else:
                            idx_start = len(tweet_list)
                            tweet_list.extend(tweets)
                            for idx in range(idx_start, len(tweet_list)):
                                if tweet_list[idx].id_str == since:
                                    found = 1
                                    return tweet_list[:idx]
                            last = tweet_list[-1].id - 1
                            done = 1
                    except tweepy.RateLimitError:
                        print "%s get_timeline_since() rate limit error" % self.name
                        self.wait_limit_reset('timeline')
                    except tweepy.TweepError:
                        return tweet_list
                else:
                    self.wait_limit_reset('timeline')
                
        if verbose:
            for tweet in tweet_list:
                print tweet.text

        return tweet_list
        
            
    def get_timeline(self, userid=None, n=20, verbose=0):
        """
        Gets n most recent tweets posted by the specified user
        
        Arguments:
        1. userid - user ID or screen_name (if None, then user is this bot)
        2. n - number of tweets to get        
        
        Returns: 
        1. list of TWEET objects     
        """
        
        tweet_list = []
        
        done = 0        
        while done == 0:
            # initial acquisition
            if ( self.remaining['timeline'] != 0 ):
                if n > 200:
                    num = 200
                    n = n - 200
                else:
                    num = n
                    n = 0
                try:
                    tweets = self.api.user_timeline(userid, count=num)
                    self.remaining['timeline'] -= 1
                    tweet_list.extend(tweets)
                    if tweet_list != []:
                        # starting point of next acquisition                    
                        last = tweet_list[-1].id - 1
                    done = 1
                except tweepy.RateLimitError:
                    print "%s get_timeline() rate limit error" % self.name
                    self.wait_limit_reset('timeline')
                except tweepy.TweepError:
                    return tweet_list
                except Exception as e:
                    print userid
                    print e
            else:
                self.wait_limit_reset('timeline')

        # While number of remaining tweets to get is not 0
        while n != 0 and len(tweets) != 0:
            done = 0
            while done == 0:
                if ( self.remaining['timeline'] != 0 ):
                    if n > 200:
                        num = 200
                        n = n - 200
                    else:
                        num = n
                        n = 0
                    try:
                        tweets = self.api.user_timeline(userid, count=num, 
                                                            max_id=last)
                        self.remaining['timeline'] -= 1
                        tweet_list.extend(tweets)
                        last = tweet_list[-1].id - 1
                        done = 1     
                    except tweepy.RateLimitError:
                        print "%s get_timeline() rate limit error" % self.name
                        self.wait_limit_reset('timeline')
                    except tweepy.TweepError:
                        return tweet_list
                else:
                    self.wait_limit_reset('timeline')
                
        if verbose:
            for tweet in tweet_list:
                print tweet.text

        return tweet_list


    def get_by_hashtag(self, tag, n, verbose=0):
        """
        Retrieves the latest N tweets with the given hashtag
        
        Argument:
        1. tag - string of the form "#<hashtag_to_search_for>"
        2. n - Number of tweets to find
        
        Return: 
        1. list of TWEET objects
        """

        tweet_list = []     
    
        # initial acquisition
        done = 0
        while done == 0:
            if ( self.remaining['search'] != 0 ):
                if n > 15:
                    num = 15
                    n = n - 15
                else:
                    num = n
                    n = 0
                try:
                    tweets = self.api.search(tag, count=num)
                    self.remaining['search'] -= 1
                    tweet_list.extend(tweets)
                    # starting point of next acquisition
                    if len(tweet_list) != 0:
                        last = tweet_list[-1].id - 1
                    done = 1
                except tweepy.RateLimitError:
                    print "%s get_by_hashtag() rate limit error" % self.name
                    self.wait_limit_reset('search')
                except tweepy.TweepError:
                    return tweet_list
            else:
                self.wait_limit_reset('search')

        # While number of remaining tweets to get is not 0
        while n != 0 and len(tweets) != 0:
            done = 0
            while done == 0:
                if ( self.remaining['search'] != 0 ):
                    if n > 15:
                        num = 15
                        n = n - 15
                    else:
                        num = n
                        n = 0
                    try:
                        tweets = self.api.search(tag, count=num, 
                                                 max_id=last)
                        self.remaining['search'] -= 1
                        tweet_list.extend(tweets)
                        last = tweet_list[-1].id - 1
                        done = 1
                    except tweepy.RateLimitError:
                        print "%s get_by_hashtag() rate limit error" % self.name
                        self.wait_limit_reset('search')
                    except tweepy.TweepError:
                        return tweet_list
                else:
                    self.wait_limit_reset('search')
                
        if verbose:
            for tweet in tweet_list:
                print tweet.text

        return tweet_list


    def get_likers(self, post_id):
        """
        Get list of ids of users who liked a tweet by this bot
        
        Argument:
        1. post_id - id of tweet by bot
        
        Return:
        list of ids
        
        Limitation: only returns at most 25 liker IDs
        """
        
        try:
            json_data = urllib2.urlopen('https://twitter.com/i/activity/favorited_popup?id=' + str(post_id)).read()
            found_ids = re.findall(r'data-user-id=\\"+\d+', json_data)
            unique_ids = list(set([re.findall(r'\d+', match)[0] for match in found_ids]))
            return unique_ids
        except urllib2.HTTPError as err:
            print "%s get_likers() error: " % self.name, err
            return []
        except:
            print "%s get_likers() error: " % self.name
            return []


    def get_retweets(self, tweet_list, verbose=0):
        """
        For all tweets in tweet_list, get details of the retweet
        
        Argument:
        tweet_list - list of tweet id_str
        verbose - optionally prints details of the users who retweeted
        
        Return: 
        1. dictionary from tweet ID to list of tuples.
        Each list is associated with a single tweet ID
        Each tuple within the list is ( retweeter id_str, datetime of retweet )
                        
        Limitation: only returns 100 of the first retweets of the given tweet
        """

        return_dic = {}
          
        for tweet_id in tweet_list:
            done_inner = 0
            while done_inner == 0:
                if ( self.remaining['retweets'] != 0 ):
                    try:
                        # up to 100 of the first retweets of the given tweet
                        retweet_list = self.api.retweets(tweet_id, count=100, trim_user=True)
                        self.remaining['retweets'] -= 1
                    except tweepy.RateLimitError:
                        print "%s get_retweets() rate limit error" % self.name
                        self.wait_limit_reset('retweets')
                        continue
                    except tweepy.TweepError:
                        # reached rate limit, stop iterating
                        return return_dic                  
                    
                    # Create list to store all tuples associated with this tweet
                    tuple_list = []
                        
                    for retweet in retweet_list:
                        retweeter_id_str = retweet.user.id_str
                        # retweet.created_at is UTC time, which is 4 hours ahead of EST
                        date = retweet.created_at + datetime.timedelta(hours=-4)
                                            
                        # Create tuple containing details of the retweet
                        # and store into list of tuples
                        tuple_list.append( (retweeter_id_str, date) )
                        
                        if verbose:
                            print "Retweeted by user id_str: %s" % (retweeter_id_str)
                            print "Timestamp: %d/%d/%d %d:%d:%d" % (date.month, date.day,
                                                                    date.year, date.hour,
                                                                    date.minute, date.second)
                            print "Text of retweet: %s" % retweet.text
                    # Store list of tuples into dictionary, associated with the ID
                    # of the original tweet
                    return_dic[tweet_id] = tuple_list
                    done_inner = 1
                else: # api.retweets reached limit
                    self.wait_limit_reset('retweets')

            
        return return_dic


    def get_retweets_single(self, tweet_id, verbose=0):
        """
        Get retweets of the given tweet
        
        Argument:
        tweet_id - id_str of tweet
        verbose - optionally prints details of the users who retweeted
        
        Return: 
        1. list of tuples. Each tuple within the list is 
        ( retweeter id_str, datetime of retweet )
                        
        Limitation: only returns 100 of the first retweets of the given tweet
        """

        # Create list to store all tuples associated with this tweet
        list_tuples = []
        done = 0
        while done == 0:
            if ( self.remaining['retweets'] != 0 ):
                try:
                    # up to 100 of the first retweets of the given tweet
                    retweet_list = self.api.retweets(tweet_id, count=100, trim_user=True)
                    self.remaining['retweets'] -= 1
                except tweepy.RateLimitError:
                    print "%s get_retweets_single() rate limit error" % self.name
                    self.wait_limit_reset('retweets')
                    continue
                except tweepy.TweepError as err:
                    print "Error in rlbot.get_retweets_single(): ", err
                    return list_tuples
                except Exception as e:
                    print tweet_id
                    print e
                
                for retweet in retweet_list:
                    retweeter_id_str = retweet.user.id_str
                    # retweet.created_at is UTC time, which is 4 hours ahead of EST
                    date = retweet.created_at + datetime.timedelta(hours=-4)
                                        
                    # Create tuple containing details of the retweet
                    # and store into list of tuples
                    list_tuples.append( (retweeter_id_str, date) )
                    
                    if verbose:
                        print "Retweeted by user id_str: %s" % (retweeter_id_str)
                        print "Timestamp: %d/%d/%d %d:%d:%d" % (date.month, date.day,
                                                                date.year, date.hour,
                                                                date.minute, date.second)
                        print "Text of retweet: %s" % retweet.text
                done = 1
            else: # api.retweets reached limit
                self.wait_limit_reset('retweets')
            
        return list_tuples


    def get_retweets_all(self, verbose=0):
        """
        For all tweets by the bot that was retweeted, get details of the retweet
        
        Argument:
        verbose - optionally prints details of the users who retweeted
        
        Return: 
        1. dictionary from tweet ID to list of tuples.
        Each list is associated with a single tweet ID
        Each tuple within the list is ( retweeter id_str, datetime of retweet )
                        
        PROBLEM: currently only returns 100 of the first retweets of the given tweet
        """

        return_dic = {}
        done = 0
        
        while done == 0:
            if ( self.remaining['retweets_of_me'] != 0 ):
                try:
                    # 100 most recent tweets by bot that have been retweeted by others
                    tweet_list = self.api.retweets_of_me(count=100)
                    self.remaining['retweets_of_me'] -= 1
                except tweepy.TweepError:
                    return return_dic
                
                for tweet in tweet_list:
                    # string representation of the unique identifier of this tweet
                    bot_tweet_id = tweet.id_str
                    done_inner = 0
                    while done_inner == 0:
                        if ( self.remaining['retweets'] != 0 ):
                            try:
                                # up to 100 of the first retweets of the given tweet
                                retweet_list = self.api.retweets(bot_tweet_id, count=100, trim_user=True)
                                self.remaining['retweets'] -= 1
                            except tweepy.TweepError:
                                # reached rate limit, stop iterating
                                return return_dic                  
                            
                            # Create list to store all tuples associated with this tweet
                            tuple_list = []
                                
                            for retweet in retweet_list:
                                id_str = retweet.user.id_str
                                date = retweet.created_at
                                                    
                                # Create tuple containing details of the retweet
                                # and store into list of tuples
                                tuple_list.append( (id_str, date) )
                                
                                if verbose:
                                    print "Retweeted by user id_str: %s" % (id_str)
                                    print "Timestamp: %d/%d/%d %d:%d:%d" % (date.month, date.day,
                                                                            date.year, date.hour,
                                                                            date.minute, date.second)
                                    print "Text of retweet: %s" % retweet.text
                                            # Store list of tuples into dictionary, associated with the ID
                            # of the original tweet
                            return_dic[bot_tweet_id] = tuple_list
                            done_inner = 1
                        else: # api.retweets reached limit
                            self.wait_limit_reset('retweets')
                done = 1
            else:
                self.wait_limit_reset('retweets_of_me')
            
        return return_dic


    def set_status_from_file(self, filename):
        """
        Posts to bot's own timeline from file

        Argument:
        1. filename - path to file, each line of which is a separate post
        
        """
        f = open(filename, 'r')
        lines = f.readlines()
        f.close()
        
        for line in lines:
            done = 0
            while done == 0:
                # If not yet at limit of 25updates/15min (2400updates/day)
                if self.remaining['update'] != 0:
                    self.api.update_status(line)
                    self.remaining['update'] -= 1
                    time.sleep(self.period)
                    done = 1
                else:
                    self.wait_limit_reset('update')

    def tweet(self, text):
        """
        Makes a tweet using the given text

        Return
        1 - if successful
        0 - if encountered tweepy error
        """
        done = 0
        while done == 0:
            if self.remaining['update'] != 0:
                try:
                    self.api.update_status(text)
                    self.remaining['update'] -= 1
                    done = 1
                    return 1
                except tweepy.TweepError as err:
                    print "Error in rlbot.tweet(): ", err
                    return 0
            else:
                self.wait_limit_reset('update')

    def retweet(self, id_str):
        """
        Retweets the tweet with the given id_str
        """
        done = 0
        while done == 0:
            if self.remaining['update'] != 0:
                self.api.retweet(id_str)
                done = 1
            else:
                self.wait_limit_reset('update')


    def follow(self, id):
        """
        Follows all accounts in list_of_ids.
        Rate limit is 1000/day, which is 41/hour, which requires waiting
        90seconds between each follow

        Return code: 1 if error, else 0
        """
        done = 0
        while done == 0:
            try:
                self.api.create_friendship(id)
                done = 1
                return 0
            except tweepy.RateLimitError:
                print "%s follow() rate limit error" % self.name
                time.sleep(90)
            except tweepy.TweepError as err:
                print "%s follow() error: " % self.name, err
                try:
                    if err[0][0]['code'] == 108:
                        # could not find specified user, ignore and proceed
                        return 0
                    elif err[0][0]['code'] == 160:
                        # already requested to follow user, ignore and continue
                        return 0
                    elif err[0][0]['code'] == 162:
                        # user blocked bot accounts from following
                        return 0
                    elif err[0][0]['code'] == 326:
                        # account temporarily locked
                        return 1
                    else:
                        return 1
                except:
                    return 0
            except Exception as e:
                print userid
                print e
                return 1


    def get_trends_place(self, woeid=2357024, expected_location_name='Atlanta'):
        """
        Argument:
        1. woeid - id of location
        2. expected_location_name - name of location corresponding to woeid,
        used as a check that the returned object by the API corresponds to the 
        expected location

        Returns:
        1. list of trend objects
        """
        list_trends = []
        done = 0
        while done == 0:
            if (self.remaining['trends_place'] != 0):
                try:
                    trends_dict = self.api.trends_place(woeid)[0]
                    if trends_dict['locations'][0]['name'] != expected_location_name:
                        print "%s get_trends_place() location mismatch" % self.name
                    self.remaining['trends_place'] -= 1
                    list_trends = trends_dict['trends']
                    done = 1
                except tweepy.RateLimitError:
                    print "%s get_trends_place() rate limit error" % self.name
                    self.wait_limit_reset('trends_place')
                except tweepy.TweepError:
                    return list_trends
            else:
                self.wait_limit_reset('trends_place')

        return list_trends


    def monitor(self, id_list, duration, period):
        """
        Periodically sample timeline of user and acquire all tweets
        and retweets by that user starting from the time when this function is run
        
        Arguments:
        1. id_list - list of userids of accounts to monitor
        2. duration - length of time to run this function (unit: hours)
        3. period - sampling period (unit: minutes)
        
        Return:
        Dictionary from id to list of tuples.
        Each list of tuples is ordered in time from earliest to most recent
        Each tuple is (tweet ID, text of tweet, time of tweet [date,hour,minute,second],
                       number of likes)
        Also prints to csv file
        """
        
        # Create report files and write headers
        for userid in id_list:
            f = open("monitor_%s.csv" % userid, "w")
            s = "userid,time,tweetID,text,num_likes,num_retweets\n"    
            f.write(s)
            f.close()        

        t_start = time.time()
        # Starting time of 15min window
        t_window_start = t_start
        
        # Mapping from userid to the ID of the last recorded post by that user
        map_userid_lastID = {}
        # Get id_str of the most recent tweet, start monitoring all tweets after this one
        for userid in id_list:
            tweet_list = bot.get_timeline(userid, n=1, verbose=0)
            map_userid_lastID[userid] = tweet_list[0].id_str
        
        # Continuous monitoring
        while True:
            if ( time.time() - t_start ) > duration * 60 * 60:
                break
            else:
                # Every 15minutes, reset the count of remaining requests allowed
                if ( time.time() - t_window_start ) > 15*60:
                    t_window_start = time.time()
                    # Reset API request limits
                    bot.update_limits()                
                    
                for userid in id_list:
                    # Get all tweets since the last recorded tweet
                    tweets = self.get_timeline_since(userid, since=map_userid_lastID[userid], verbose=0)

                    f = open("monitor_%s.csv" % userid, "a")
                    # Append to file, oldest first
                    for tweet in tweets[::-1]:  
                        s = "%s,%s,%s,%s,%d,%d\n" % (userid, tweet.created_at.strftime('%Y-%m-%d %H:%M:%S'), 
                                                     tweet.id_str, tweet.text, tweet.favorite_count, 
                                                     tweet.retweet_count)
                        print s                                                
                        f.write(s.encode('utf8'))
#                        f.write("%s,%s,%s,%s,%d,%d\n" % (userid, tweet.created_at.strftime('%Y-%m-%d %H:%M:%S'),
#                                                 tweet.id_str, tweet.text, tweet.favorite_count,
#                                                 tweet.retweet_count))
                    f.close()
                    # Store ID of most recent new tweet, if any
                    if len(tweets) != 0:
                        map_userid_lastID[userid] = tweets[0].id_str
                    
                time.sleep(period*60)
                

    def checker(self):
        t_start = time.time()
        while True:
            if ( time.time() - t_start ) > self.duration*60:
                break
            else:
                # Every 15minutes, reset the count of remaining requests allowed
                if ( time.time() - self.tstart ) > 15*60:
                    self.tstart = time.time()
                    # Reset API request limits
                    self.update_limits()
                    
                for idx in range(0, 20):
                    lis = self.get_followers()
                    if idx == 0:
                        print "Followers: idx = %d | len = %d" % (idx, len(lis))
                for idx in range(0, 185):
                    lis = self.get_timeline()
                    if idx == 0:
                        print "Timeline: idx = %d | len = %d" % (idx, len(lis))
                for idx in range(0, 185):
                    lis = self.get_by_hashtag('#gtml', 5)
                    if idx == 0:
                        print "Search: idx = %d | len = %d" % (idx, len(lis))
                for idx in range(0, 65):
                    dic = self.get_retweets(2,3, verbose=0)
                    if idx == 0: 
                        print "Retweet: idx = %d | len = %d" % (idx, len(dic))
                for idx in range(0, 20):
                    dic = self.get_retweets_all(verbose=0)
                    if idx == 0:
                        print "Retweets_of_me: idx = %d | len = %d" % (idx, len(dic))
                # wait 15 minutes plus some margin
                time.sleep(15*60 + 5)
    

if __name__ == "__main__":
    
    bot = rlbot('matt_learner', 'key_ml.txt')
