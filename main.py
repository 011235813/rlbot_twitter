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

# Import reinforcement learning algorithm
# import algorithm

class main:

    def __init__(self, init_bots=1, init_observer=1):
        
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
        self.generate_observation_time( (11,15,0), (11,20,0), 6 )
        
        # Map from ID of follower F_i of bot --> list L consisting of all the friends of
        # that F_i (i.e. everyone followed by F_i), including the bot itself
        self.map_follower_friend = {}

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
#        self.num_like_prev[bot_id] = sum(like_list)
#        self.num_retweet_prev[bot_id] = sum(retweet_list)
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
        
    
    def observe_follower_friend(self):
        for follower_id in self.bot.followers:
            list_friend_id = self.bot.get_friends(userid=follower_id)
            self.map_follower_friend[follower_id] = list_friend_id

    
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
        list_first_person = ["we've", "we", "we'll", "our", "me", "my"]
        
        # Binary list, element L_i indicates whether tweet_i has been checked
        list_checked = [0 for idx in range(0,num)]
        while not done:
            idx_tweet = random.randrange(0, num)
            list_checked[idx_tweet] = 1
            text = source_timeline[idx_tweet].text
            text_lower = text.lower()
            violate = 0
            # Check for violation of the rule
            for word in list_first_person:
                if word in text_lower:
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
        if attribute:
            text = "From %s: %s" % (source_name, text)

        # Trim to character limit
        if len(text) > 140:
            text = text[:140]
        self.bots[bot_id].tweet(text)

        # Wait for tweet to appear on twitter, then get the id_str that twitter
        # assigned to it
        time.sleep(5)
        id_str_mine = self.bots[bot_id].get_timeline(self.bots[bot_id].name, n=1)[0].id_str
        
        if verbose:
            print "Bot %d" % bot_id
            print "%s : %s" % (source_name, text)
    
        # Update memory with new tweet
        self.all_tweet[bot_id].append(id_str_mine)
        self.map_bot_tweet_prev[bot_id].put(id_str_mine)
        
        return id_str_mine
        
    
    def record_last_tweet(self, bot_id, tweet_id_str):
        current_time = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        f = open( "tweet_%d.txt" % bot_id, "a" )
        f.write("%s,%s" % (tweet_id_str, current_time))
        f.write("\n")
        f.close()
       
    # Record the response to a previous action   
    def record(self, bot_id):
        
        # Extract the id_str of the last tweet of this bot from the queue
        tweet_id_str = self.map_bot_tweet_prev[bot_id].get()
        
        # Number of likes, retweets, followers
        # Format of records.csv is
        # id_str of previous tweet, # likes, # retweets, # followers
        num_like_prev, num_retweet_prev = self.observe_num_like_retweet(bot_id, tweet_id_str)
        self.bots[bot_id].update_followers()
        f = open( "records_%d.csv" % bot_id, 'a' )
        
        f.write("%s,%d,%d,%d\n" % (tweet_id_str, num_like_prev, 
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
        f = open( "retweeters_%d.csv" % bot_id, 'a' )        
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
        f = open( "likers_%d.csv" % bot_id, 'a' )            
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
        
        # Generate list for each bot
        for bot_id in range(0, 4+1):
        
            # Initialize list
            list_time = [0 for idx in range(0, N)]        
        
            # Generate N random times in seconds
            for idx in range(0, N):
                t_random_sec = int(round(t_start_sec + random.random() * delta))
                minute, second = divmod(t_random_sec, 60)
                hour, minute = divmod(minute, 60)
                list_time[idx] = (hour, minute, second)

            # Sort into chronological order and store into map   
            list_time.sort()
            print "Bot %d" % bot_id
            print list_time
            self.map_bot_action_time[bot_id] = list_time        
        

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

        # Generate N random times in seconds
        for idx in range(0, N+1):
            t_sec = t_start_sec + idx*delta
            minute, second = divmod(t_sec, 60)
            hour, minute = divmod(minute, 60)
            print (hour, minute, second)
            self.observation_time.append( (hour, minute, second) )


    def get_wait_time(self):
        # Returns (hour, min), which specifies how long the bot should wait
        # after making a post before it measures the response

        # Placeholder of 2 hours 0 minutes and 0 seconds
        return (0,5,0)

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
                
                
    def run(self, total_day):
        """
        Main program that schedules and executes all events for the entire
        duration of the experiment
        
        Argument:
        1. total_day - total number of days to run the system
        """        
        
        # Time to wait between making tweet and observing response
        wait_time = self.get_wait_time()        
        
        num_day = 0
        
        # Update the set of people to track
        self.observer.update_tracking( ['ml%d_gt' % idx for idx in range(1,5+1)] )
        list_to_track = list(self.observer.tracking)
        list_to_track.sort()

        # Each iteration of this loop is a day
        while num_day < total_day:
        
            num_day += 1
            print "Day %d" % num_day
        
            # At start of this day, update the set of people to track
            self.observer.update_tracking( ['ml%d_gt' % idx for idx in range(1,5+1)] )
            list_to_track = list(self.observer.tracking)
            list_to_track.sort()
        
            # Store the last tweet made by each follower of the bots
            map_follower_lasttweet = {}
            f = open("tracker_day%d.csv" % num_day, 'a')
            s = "Time,"
            for follower_id_str in list_to_track:
                s += "%s," % follower_id_str
                tweet_list = self.observer.get_timeline(follower_id_str, n=1, verbose=0)
                if len(tweet_list) != 0:
                    map_follower_lasttweet[follower_id_str] = tweet_list[0].id_str
                else:
                    map_follower_lasttweet[follower_id_str] = ''
            s += "\n"
            f.write(s)
            f.close()        
        
            # At the start of each day, generate the entire set of action times
            # for all bots
#            self.generate_post_time_random( (8,0,0), (22,0,0), 3 ) here
            self.generate_post_time_random( (11,15,0), (11,20,0), 1 )

            # NOTE: this method of putting action events into the queue all at once is only
            # correct for the version of the system that does not use the algorithm
            # to generate action times. 
            # Store all action times into priority queue
            # For each action time, include information on which bot is associated
            # with the time, and indicate that the event type is action 'a'
            for bot_id in range(0, 4+1):
                list_time = self.map_bot_action_time[bot_id]
                for t_action in list_time:
                    self.event_queue.put( (t_action, bot_id, 'a') )
        
            # Insert main observation events into the queue
            # The main observation bot has ID=5 (IDs start from 0)
            for idx in range(0, len(self.observation_time)):
                self.event_queue.put( (self.observation_time[idx], 5, 'o_main') )
        
            print self.event_queue.qsize()   
        
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
                    self.record_last_tweet(event_bot, bot_tweet_id_str)
                    
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
                    # main observation event (i.e. every hour)
                    f = open("tracker_day%d.csv" % num_day, 'a')
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
                            map_follower_lasttweet[follower_id_str] = tweet_list[0].id_str
                        

                        f.write("%d," % len(tweet_list))
                    f.write("\n")
                        
            
            # Sleep until 00:00:10 of next day
            current_time = datetime.datetime.now()
            sec_until_tomorrow = 24*3600 - (current_time.hour*3600 + current_time.minute*60 \
                                            + current_time.second)                                            
            time.sleep(sec_until_tomorrow + 10)
            
           

if __name__ == "__main__":
    
    exp = main(init_bots=1, init_observer=1)
