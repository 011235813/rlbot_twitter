# -*- coding: utf-8 -*-
"""
Created on Thu Sep 15 12:32:08 2016

@author: jiachen.yang@gatech.edu
"""

import rlbot

import time
import random
import datetime
from operator import itemgetter
import Queue
import os

# Import reinforcement learning algorithm
# import algorithm

class main:

    def __init__(self, init_bots=1, init_observer=1, logfile='/home/t3500/devdata/rlbot_data/log.txt'):
        
        self.logfilename = logfile

        # List of bots
        self.bots = []
        if init_bots:
            for idx in range(1, 5+1):
                self.bots.append( rlbot.rlbot(name="ml%d_gt"%idx, keyfile="key_bot%d.txt"%idx) )
        
        if init_observer:
            self.observer = rlbot.rlbot('matt_learner', 'key_ml.txt')

        # List of times to observe activity of followers
        # This is independent of the observations made by each bot
        # Each bot is responsible for observing the response to its own tweets
        self.observation_time = []
        self.generate_observation_time( (0,30,0), (23,30,0), 23 )
        # self.generate_observation_time( (19,25,0), (19,30,0), 5 )

        # Map from bot_id to Queue of tweet id_str by that bot
        # Each element in the queue is the id_str of a tweet made earlier, that 
        # still requires a measurement of the response
        self.map_bot_tweet_prev = { idx:Queue.Queue() for idx in range(0,4+1) }
        
        # Map bot_id --> list of id_str of all tweets that the bot has posted during lifetime
        self.all_tweet = { idx:[] for idx in range(0,4+1) }

        # List of screen_name of accounts whose tweets will be copied 
        # and tweeted by the bot
        self.list_source = []
        self.populate_source( 'source.txt' )
        
        # Priority queue whose elements are tuples (time_tuple, bot_id, event_type)
        # Shared among all bots (bot_0,...bot_4,bot_5) in order to correctly
        # serialize the event sequence
        self.event_queue= Queue.PriorityQueue(maxsize=-1)
        
        # Map from bot_id --> list of times when that bot is supposed to post
        # This is necessary for the first part of the experiment, when all 
        # post times are random, rather than queried from the algorithm 
        # in stages. 
        self.map_bot_action_time = { idx:[] for idx in range(0,4+1)}

    def write_headers(self):
        """
        Writes headers of records_*.csv log file

        Note that retweets_*.csv, likers_*.csv and tracker_day*.csv
        do not have headers because the number of columns is dynamic
        """
        for bot_id in range(0,4+1):
            f = open( "/home/t3500/devdata/rlbot_data/records_%d.csv" % bot_id, 'a' )
            f.write("tweet_id_str,time,num_like,num_retweet,num_follower\n")
            f.close()

    def delete_all_tweets(self, all=1, bot_id=0):
        """
        Deletes tweets by bots
        """
        for id in range(0,4+1):
            if all or (all == 0 and id == bot_id):
                timeline = self.bots[id].get_timeline("ml%d_gt" % (id+1), n=100)
                for tweet in timeline:
                    self.bots[id].api.destroy_status(tweet.id)

        
    def populate_source(self, filename):
        f = open(filename, 'r')
        lines = f.readlines()
        f.close()
        for line in lines:
            self.list_source.append( line.strip() )
  
    
    def observe_num_like_retweet(self, bot_id, tweet_id_str):
        """ 
        Argument:
        1. bot_id - 0,1,2,3,4
        2. tweet_id_str
        
        Return:
        (total num of likes, total num of retweets) received by tweet_id_str
        """
        # The get_num_like_retweet function expects a list
        # In this case we're only interested in the response to a single previous
        # tweet, so the input list only has one element
        like_list, retweet_list = self.bots[bot_id].get_num_like_retweet( [tweet_id_str] )
        return sum(like_list), sum(retweet_list)
    
    
    def observe_retweeter(self, bot_id, tweet_id_str):
        """ 
        Argument:
        1. bot_id - 0,1,2,3,4
        2. tweet_id_str
        
        Return:
        List of tuples - [ (retweeter1,datetime1), (retweeter2,datetime2),....]
        associated with the input tweet
        """
        # The get_retweets function takes in a list of tweets, so here we just
        # pass in a list with one element
        map_tweet_retweeter = self.bots[bot_id].get_retweets( [tweet_id_str] )
        return map_tweet_retweeter[tweet_id_str]

    
    def observe_liker(self, bot_id, tweet_id_str):
        """ 
        Argument:
        1. bot_id - 0,1,2,3,4
        2. tweet_id_str
        
        Return:
        List of id_str of people who liked the input tweet
        """
        return self.bots[bot_id].get_likers(tweet_id_str)
        
    
    def choose_tweet(self, source_timeline):
        """
        Additional processing of the raw text copied from the source's timeline
        From all the tweets in source_timeline, attempt to find a random tweet
        that does not contain any variant of a first-person pronoun.
        
        Argument:
        1. source_timeline - list of posts by the source
        
        Return
        processed text string
        """
        done = 0
        num = len(source_timeline)
        list_first_person = ["we've", "we", "we'll", "our", "me", "my", 
                             "us", "i", "i'll", "you"]
        
        # Binary list, element L_i indicates whether tweet_i has been checked
        list_checked = [0 for idx in range(0,num)]
        while not done:
            idx_tweet = random.randrange(0, num)
            list_checked[idx_tweet] = 1
            text = source_timeline[idx_tweet].text
            list_token = text.lower().split()
            violate = 0
            # Check for violation of the rule
            for word in list_first_person:
                if word in list_token:
                    violate = 1
                    break
            if violate == 0:
                # If no violation was found, return this tweet
                return text
            else:
                # Exists violation
                if sum(list_checked) == num:
                    # If all tweets in source_timeline have been checked
                    # and still cannot find a tweet that passes the criteria,
                    # then just return the text
                    return text


    def process_tweet(self, input_text):
        """
        Fix links, formatting, extraneous substrings, etc.
        """

        # If the post was a retweet, then the raw text 
        # will have format "RT @someone: <The actual text>"
        # Therefore, remove everything before the actual text
        if ("RT " in input_text):
            idx = input_text.index(":")
            return input_text[idx+2:]
        else:
            return input_text

    
    # Bot's action    
    def act(self, bot_id, attribute=0, verbose=0):
        """
        Performs action at each stage: 
        1. From list of source accounts, randomly choose one
        2. From that source's timeline, randomly choose a tweet
        3. Copy the message of the tweet and post it as the bot's original content
        
        Argument:
        1. bot_id - 0,1,2,3,4
        2. attribute - if 1, then attributes the source of the text by
        prepending "From <user>:" to the start of the bot's post
        3. verbose - if 1, prints the text of the bot's tweet to the console
        
        Return:
        id_str of the tweet made by bot
        
        """
        
        idx_source = random.randrange(0, len(self.list_source))
        source_name = self.list_source[idx_source]
        
        # Get the 5 most recent posts by the source
        source_timeline = self.bots[bot_id].get_timeline(source_name, 5)

        # Randomly select a tweet
        text = self.choose_tweet(source_timeline)
        # Additional text processing
        text = self.process_tweet(text)
        if attribute:
            text = "From %s: %s" % (source_name, text)

        # Trim to character limit
        if len(text) > 140:
            text = text[:140]
        # Before making new tweet, make note of the most recent tweet
        tl = self.bots[bot_id].get_timeline(self.bots[bot_id].name, n=1)
        if len(tl):
            id_str_prev = tl[0].id_str
        else:
            id_str_prev = '0'
        # Now make new tweet
        self.bots[bot_id].tweet(text)

        # Log the time when bot made the tweet
        time_of_tweet = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')

        # Wait for tweet to appear on twitter, then get the id_str that twitter
        # assigned to it
        time.sleep(5)
        done = 0
        t_start = time.time()
        while not done:
            # Hard cap of 10 seconds, resort to the most recent tweet
            if ( time.time() - t_start > 10 ):
                id_str_mine = id_str_prev
                break
            # Get most recent tweet
            id_str_mine = self.bots[bot_id].get_timeline(self.bots[bot_id].name, n=1)[0].id_str
            if id_str_mine != id_str_prev:
                # Most recent tweet changed, meaning the new tweet was successful
                done = 1
            else:
                # Wait a little more for the new tweet to appear
                time.sleep(1)
        
        f = open(self.logfilename, "a")
        f.write("Bot %d\n" % bot_id)
        f.write("%s : %s\n" % (source_name, text.encode('utf8')))
        f.close()

        if verbose:
            print "Bot %d" % bot_id
            print "%s : %s" % (source_name, text)
    
        # Update memory with new tweet
        self.all_tweet[bot_id].append(id_str_mine)
        # Store tweet_id and time of tweet into the queue of actions that still
        # require recording of response
        self.map_bot_tweet_prev[bot_id].put([id_str_mine, time_of_tweet])
        return id_str_mine
        
    
    def record_last_tweet(self, bot_id, tweet_id_str):
        current_time = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        f = open( "/home/t3500/devdata/rlbot_data/tweet_%d.txt" % bot_id, "a" )
        f.write("%s,%s" % (tweet_id_str, current_time))
        f.write("\n")
        f.close()
       
    # Record the response to a previous action   
    def record(self, bot_id):
        
        # Extract the id_str of the last tweet of this bot from the queue
        pair = self.map_bot_tweet_prev[bot_id].get()
        tweet_id_str = pair[0]
        tweet_time = pair[1]
        
        # Number of likes, retweets, followers
        # Format of records.csv is
        # id_str of previous tweet, # likes, # retweets, # followers
        num_like_prev, num_retweet_prev = self.observe_num_like_retweet(bot_id, tweet_id_str)
        self.bots[bot_id].update_followers()
        f = open( "/home/t3500/devdata/rlbot_data/records_%d.csv" % bot_id, 'a' )
        f.write("%s,%s,%d,%d,%d\n" % (tweet_id_str, tweet_time, num_like_prev, 
                                 num_retweet_prev, 
                                 self.bots[bot_id].num_followers))
        f.close()
        
        # Retweeter info
        # Format of retweeters_*.csv is
        # tweet id_str, retweeter1 id_str, datetime1, retweeter2 id_str, datetime2, and so on
        list_retweeter_info = self.observe_retweeter(bot_id, tweet_id_str)
        s = "%s," % tweet_id_str
        for retweeter in list_retweeter_info:
            retweeter_id_str = retweeter[0]
            retweeter_datetime = retweeter[1].strftime('%Y-%m-%d-%H-%M-%S')
            s += "%s,%s," % (retweeter_id_str, retweeter_datetime)
        s += "\n"
        f = open( "/home/t3500/devdata/rlbot_data/retweeters_%d.csv" % bot_id, 'a' )        
        f.write(s)
        f.close()
        
        # Liker info
        # Format of likers.csv is
        # tweet id_str, liker1 id_str, liker2 id_str, and so on
        list_liker = self.observe_liker(bot_id, tweet_id_str)
        s = "%s," % tweet_id_str
        for liker_id_str in list_liker:
            s += "%s," % liker_id_str
        s += "\n"
        f = open( "/home/t3500/devdata/rlbot_data/likers_%d.csv" % bot_id, 'a' )            
        f.write(s)            
        f.close()


    def generate_post_time_random(self, t_start, t_end, N):
        """
        Generate N tuples representing time, randomized, from t_start to t_end
        for each bot. Stores resulting list of times into self.map_bot_action_time
        
        Argument:
        t_start - time of day as a tuple (hour, min, sec)
        t_end - time of day as a tuple (hour, min, sec)
        N - number of randomized times between t_start and t_end
        """
        
        # Convert to seconds
        t_start_sec = t_start[0]*3600 + t_start[1]*60 + t_start[2]
        t_end_sec = t_end[0]*3600 + t_end[1]*60 + t_end[2]        
        
        delta = t_end_sec - t_start_sec
        # Check that inputs make sense
        if (delta <= 0):
            return
        
        f = open(self.logfilename, "a")

        # Generate list for each bot
        for bot_id in range(0, 4+1):
            f.write("Bot %d tweet times\n" % bot_id)

            # Initialize list
            list_time = [0 for idx in range(0, N)]        
        
            # Generate N random times in seconds
            for idx in range(0, N):
                t_random_sec = int(round(t_start_sec + random.random() * delta))
                minute, second = divmod(t_random_sec, 60)
                hour, minute = divmod(minute, 60)
                list_time[idx] = (hour, minute, second)
                f.write("%d,%d,%d\n" % (hour, minute, second))

            # Sort into chronological order and store into map   
            list_time.sort()
            print "Bot %d" % bot_id
            print list_time
            self.map_bot_action_time[bot_id] = list_time

        f.close()
        

    def generate_observation_time(self, t_start, t_end, N):
        """
        Generates N tuples representing time, linearly spaced, 
        from t_start to t_end, inclusive.
        Stores resulting list of times into self.observation_time
        
        Argument
        1. t_start - time of day as a tuple (hour, min, sec)
        2. t_end - time of day as a tuple (hour, min, sec)
        3. N - number of points in time to generate
        """
        # Convert to seconds
        t_start_sec = t_start[0]*3600 + t_start[1]*60 + t_start[2]
        t_end_sec = t_end[0]*3600 + t_end[1]*60 + t_end[2]        
        
        delta = int(round( (t_end_sec - t_start_sec)/N ))
        # Check that inputs make sense
        if (delta <= 0):
            return

        f = open(self.logfilename, 'a')
        f.write("Generating observation times\n")

        for idx in range(0, N+1):
            t_sec = t_start_sec + idx*delta
            minute, second = divmod(t_sec, 60)
            hour, minute = divmod(minute, 60)
            f.write("%d,%d,%d\n" % (hour, minute, second))
            # print (hour, minute, second)
            self.observation_time.append( (hour, minute, second) )

        f.close()


    def get_wait_time(self):
        # Returns (hour, min), which specifies how long the bot should wait
        # after making a post before it measures the response

        # Placeholder of 1 hours 0 minutes and 0 seconds
        return (1,0,0)

#    def calc_observation_time(self, map_bot_action_seq):
#        """
#        Given mapping from bot to list of action times, returns mapping from
#        bot to list of observation times
#        """
#        wait_time = self.get_wait_time()
#        
#        map_bot_observe_seq = {}
#        keys = map_bot_action_seq.keys()
#        
#        for bot_id in keys:
#
#            action_seq = map_bot_action_seq[bot_id]
#            observe_seq = []
#
#            for t_action in action_seq:
#                # Merely using the addition capability of the datetime package
#                datetime_action = datetime.datetime(2016,1,1,t_action[0],t_action[1],t_action[2])
#                datetime_observe = datetime_action + \
#                                    datetime.timedelta(hours=wait_time[0], minutes=wait_time[1], seconds=wait_time[2])
#                observe_seq.append( (datetime_observe.hour, datetime_observe.minute, datetime_observe.second) )
#            
#            map_bot_observe_seq[bot_id] = observe_seq
#            
#        return map_bot_observe_seq


#    def serialize(self, mapping, map_type='a'):
#        """
#        Given mapping from bot_id to list of time tuples, returns a list
#        L = [ (time tuple 1, bot 1, map_type), ... , (time tuple T, bot N, map_type) ]
#        """
#        
#        to_return = []
#        keys = mapping.keys()
#        
#        for bot_id in keys:
#            time_sequence = mapping[bot_id]
#            for t_tuple in time_sequence:
#                to_return.append( (t_tuple, bot_id, map_type) )
#
#        return to_return
                
    def is_after_now(self, now, time_tuple):
        """
        Tests whether the given time_tuple occurs after now
        Argument:
        now - datetime object
        time_tuple - tuple in the form (hour, minute, second)

        Return
        boolean
        """
        if (now.hour < time_tuple[0]):
            return 1
        elif (now.hour == time_tuple[0]):
            if (now.minute < time_tuple[1]):
                return 1
            elif (now.minute == time_tuple[1]):
                if (now.second <= time_tuple[2]):
                    return 1
                else:
                    return 0
            else:
                return 0
        else:
            return 0


    def record_network(self, list_followers, day):
        """
        Run once per day. Creates the connection matrix A for the set of followers
        of the bot.
        A_ij = 1 iff follower_i follows follower_j
        Stores results in matrix_day*.csv
        """
        
        # Create dictionary for efficiency
        map_id_index = {}
        count = len(list_followers)
        for index in range(0, count):
            map_id_index[ list_followers[index] ] = index

        f = open("/home/t3500/devdata/rlbot_data/matrix_day%d.csv" % day, "a")
        # Write header
        s = ","
        for id_str in list_followers:
            s += "%s," % id_str
        s += "\n"
        f.write(s)

        # Write rows of matrix
        for id_str in list_followers:
            # Get friends of this person
            list_friend = self.observer.get_friends(id_str)
            # Create row A_i, where A_ij = 1 iff the person with
            # id_str follows the person at column index j
            temp = [0 for x in range(0, count)]
            for friend_id in list_friend:
                if friend_id in map_id_index:
                    temp[ map_id_index[friend_id] ] = 1
            s = ','.join(map(str, temp))
            s = id_str + ',' + s + '\n'
            f.write(s)

        f.close()


    def observe_follower_detail(self, list_to_track, map_follower_lasttweet_day):
        """
        This function is called only at the end of a day, after event_queue has been emptied
        For each follower, append to three files:
        1. records_*.csv - tweet_id, time created, num likes, num retweets, num followers
        2. likers_*.csv - tweet_id, liker_1_id, ... , liker_n_id
        3. retweeters_*.csv - tweet_id, retweeter_1_id, time_1, ... , retweeter_n_id, time_n

        Argument
        1. list_to_track - the list of followers (refreshed at start of every day)
        2. map_follower_lasttweet_day - map from follower_id_str to id_str of the most recent post
        as recorded at the start of the day
        """
        for follower_id in list_to_track:
            last_tweet = map_follower_lasttweet_day[follower_id]
            if last_tweet != '':
                tweets = self.observer.get_timeline_since(follower_id, since=last_tweet)
            else:
                tweets = self.observer.get_timeline(follower_id, verbose=0)            

            # Write to records_*.csv
            path_to_file = "/home/t3500/devdata/rlbot_data/records_%s.csv" % follower_id
            if os.path.isfile(path_to_file):
                f = open(path_to_file, "a")
            else: # if file did not exist previously, write header
                f = open(path_to_file, "a")
                f.write("tweet_id_str,time,text,num_like,num_retweet\n")
            for tweet in tweets[::-1]:
                creation_time = tweet.created_at.strftime('%Y-%m-%d %H:%M:%S')
                text_mod = tweet.text.replace("\n", " ") # remove newlines
                s = "%s,%s,%s,%d,%d\n" % (tweet.id_str, creation_time, text_mod, tweet.favorite_count, tweet.retweet_count)
                f.write(s.encode('utf8'))
            f.close()

            list_tweet_id = [tweet.id_str for tweet in tweets]
            
            # Write to likers_*.csv
            f = open("/home/t3500/devdata/rlbot_data/likers_%s.csv" % follower_id, "a")
            for tweet_id_str in list_tweet_id[::-1]:
                s = "%s," % tweet_id_str
                list_liker = self.observer.get_likers(tweet_id_str)
                s = s + ",".join(list_liker)
                s += "\n"
                f.write(s)
            f.close()

            map_tweet_retweeter = self.observer.get_retweets( list_tweet_id )
            f = open("/home/t3500/devdata/rlbot_data/retweeters_%s.csv" % follower_id, "a")
            # Write to retweeters_*.csv
            for tweet_id_str in list_tweet_id[::-1]:
                s = "%s," % tweet_id_str
                list_retweeter_info = map_tweet_retweeter[tweet_id_str]
                for retweeter in list_retweeter_info:
                    retweeter_id_str = retweeter[0]
                    retweeter_datetime = retweeter[1].strftime('%Y-%m-%d-%H-%M-%S')
                    s += "%s,%s," % (retweeter_id_str, retweeter_datetime)
                s += "\n"
                f.write(s)
            f.close()
            

    def run(self, total_day, start_day_num=0, header=0):
        """
        Main program that schedules and executes all events for the entire
        duration of the experiment
        
        Argument:
        1. total_day - total number of days to run the system
        2. start_day_num - 0 if running the program from day 0 (ensure that log folder
        is cleared), nonzero if need to restart the program after any number of days 
        has already elapsed.
        3. header - 1 to write headers in records_*.csv
        """        
        
        if header:
            self.write_headers()

        # Time to wait between making tweet and observing response
        wait_time = self.get_wait_time()        
        
        num_day = start_day_num

        # Each iteration of this loop is a day
        while num_day < total_day:
        
            num_day += 1
            f = open(self.logfilename, "a")
            f.write("Day %d\n" % num_day)
            print "Day %d" % num_day
        
            # At start of this day, update the set of people to track
            self.observer.update_tracking( ['ml%d_gt' % idx for idx in range(1,5+1)] )
            list_to_track = list(self.observer.tracking)
            list_to_track.sort()
        
            # Map from follower_id_str --> id_str of of the last post by that follower
            # This map will be updated at every main observation event.
            # Enables recording of number of posts by follower in 1 hour intervals
            map_follower_lasttweet = {}
            # Another map from follower_id_str --> id_str of last post
            # This map DOES NOT get updated every hour.
            # It will be used at the end of the day to get all new posts that the follower
            # made during this day
            map_follower_lasttweet_day = {}
            # Write header for tracker_day*.csv
            f = open("/home/t3500/devdata/rlbot_data/tracker_day%d.csv" % num_day, 'a')
            s = "Time,"
            for follower_id_str in list_to_track:
                s += "%s," % follower_id_str
                tweet_list = self.observer.get_timeline(follower_id_str, n=1, verbose=0)
                if len(tweet_list) != 0:
                    map_follower_lasttweet[follower_id_str] = tweet_list[0].id_str
                    map_follower_lasttweet_day[follower_id_str] = tweet_list[0].id_str
                else:
                    map_follower_lasttweet[follower_id_str] = ''
                    map_follower_lasttweet_day[follower_id_str] = ''                    
            s += "\n"
            f.write(s)
            f.close()

            now = datetime.datetime.now()
        
            # At the start of each day, generate the entire set of action times
            # for all bots
            self.generate_post_time_random( (8,0,0), (22,30,0), 2 )
#            self.generate_post_time_random( (19,25,0), (19,30,0), 1 )

            # NOTE: this method of putting action events into the queue all at once is only
            # correct for the version of the system that does not use the algorithm
            # to generate action times. 
            # Store all action times into priority queue
            # For each action time, include information on which bot is associated
            # with the time, and indicate that the event type is action 'a'
            for bot_id in range(0, 4+1):
                list_time = self.map_bot_action_time[bot_id]
                for t_action in list_time:
                    if self.is_after_now( now, t_action ):
                        self.event_queue.put( (t_action, bot_id, 'a') )
        
            # Insert main observation events into the queue
            # The main observation bot has ID=5 (IDs start from 0)

            for idx in range(0, len(self.observation_time)):
                if self.is_after_now( now, self.observation_time[idx] ):
                    self.event_queue.put((self.observation_time[idx], 5, 'o_main'))
        
            # While there are remaining events for this day
            while self.event_queue.qsize():
    
                event = self.event_queue.get()
                event_time = event[0]
                event_bot = event[1]
                event_type = event[2]
                
                # Get current time
                now = datetime.datetime.now()
    
                # Seconds elapsed since the start of the day
                now_seconds = 3600*now.hour + 60*now.minute + now.second
                event_time_seconds = 3600*event_time[0] + 60*event_time[1] + event_time[2]
    
                t_delay = event_time_seconds - now_seconds
                
                # Wait until the event is supposed to occur
                if t_delay > 0:
                    print "Delay %d" % t_delay
                    time.sleep(t_delay)
                    
                # If event is an action by bot
                if event_type == 'a':
                    bot_tweet_id_str = self.act(event_bot, attribute=0, verbose=1)
                    # self.record_last_tweet(event_bot, bot_tweet_id_str)
                    
                    # Merely using the addition function of the datetime package
                    # to get the hour,minute,second of time to observe the response
                    # to this action. The year, month and day do not matter
                    datetime_action = datetime.datetime(2016,1,1,event_time[0],
                                                        event_time[1],event_time[2])
                    datetime_observe = datetime_action + datetime.timedelta(hours=wait_time[0], 
                                                                            minutes=wait_time[1],
                                                                            seconds=wait_time[2])
                    t_observe = (datetime_observe.hour, datetime_observe.minute, datetime_observe.second)
                    # Insert the observation event into the queue
                    self.event_queue.put( (t_observe, event_bot, 'o') )
                elif event_type == 'o': # If event is an observation of response
                    self.record(event_bot)
                    # Once the system incorporates the algorithm, then the
                    # code below will be needed to get the next time to make a 
                    # post, because the next time to make a post will be determined
                    # by the algorithm only after it has observed the response to the
                    # previous post.
#                    t_action = self.get_post_time(event_bot, self.num_like_prev[event_bot], 
#                                                  self.num_retweet_prev[event_bot], 
#                                                  self.num_follower[event_bot], 
#                                                  initial=0)
#                    self.event_queue.put( (t_action, event_bot, 'a') )
                elif event_type == 'o_main': 
                    # Main observation event (i.e. every hour)
                    f = open("/home/t3500/devdata/rlbot_data/tracker_day%d.csv" % num_day, 'a')
                    # Write time
                    f.write("%d-%d-%d," % (event_time[0], event_time[1], event_time[2]))
                    for follower_id_str in list_to_track:
                        last_id_str = map_follower_lasttweet[follower_id_str]
                        if last_id_str != '':
                            tweet_list = self.observer.get_timeline_since(follower_id_str, 
                                                                      since=last_id_str, 
                                                                      verbose=0)
                        else:
                            tweet_list = self.observer.get_timeline(follower_id_str, verbose=0)
                        if len(tweet_list) != 0:
                            # Update to the new most recent tweet
                            map_follower_lasttweet[follower_id_str] = tweet_list[0].id_str
                        f.write("%d," % len(tweet_list))
                    f.write("\n")

            # Record connectivity matrix
            self.record_network(list_to_track, num_day)
                        
            # Record follower details
            self.observe_follower_detail(list_to_track, map_follower_lasttweet_day)
                    
            # Sleep until 00:00:10 of next day
            current_time = datetime.datetime.now()
            sec_until_tomorrow = 24*3600 - (current_time.hour*3600 + current_time.minute*60 \
                                            + current_time.second)                                            
            time.sleep(sec_until_tomorrow + 10)
            
           

if __name__ == "__main__":
    
    exp = main(init_bots=1, init_observer=1)
