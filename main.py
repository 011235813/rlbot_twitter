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

    def __init__(self, init_bots=1, init_observer=1, sourcefile='source.txt', 
                 logfile='/home/t3500/devdata/rlbot_data/log.txt'):
        
        self.logfilename = logfile
#        self.path = '/home/t3500/devdata/rlbot_data'
#        self.path = '/home/t3500/devdata/rlbot_data_course'
#        self.path = '/home/t3500/devdata/rlbot_data_highfrequency'
        self.path = '/home/t3500/devdata/rlbot_data_secondorder'

        # List of bots
        self.bots = []
        if init_bots:
            for idx in range(1, 5+1):
                self.bots.append( rlbot.rlbot(name="ml%d_gt"%idx, keyfile="key_bot%d.txt"%idx) )
        
        if init_observer:
            self.observer = rlbot.rlbot('matt_learner', 'key_ml.txt')

        if init_bots and init_observer:
            self.bots.append( self.observer )

        # List of times to observe activity of followers
        # This is independent of the observations made by each bot
        # Each bot is responsible for observing the response to its own tweets
        self.observation_time = []
        # self.generate_observation_time( (0,30,0), (23,30,0), 23 )

        # Map from bot_id to Queue of tweet id_str by that bot
        # Each element in the queue is the id_str of a tweet made earlier, that 
        # still requires a measurement of the response
        self.map_bot_tweet_prev = { idx:Queue.Queue() for idx in range(0,4+1) }
        
        # Map bot_id --> list of id_str of all tweets that the bot has posted during lifetime
        # self.all_tweet = { idx:[] for idx in range(0,4+1) }

        # List of screen_name of accounts whose tweets will be copied 
        # and tweeted by the bot
        self.list_source = []
        self.populate_source( sourcefile )
        
        # Map from bot_id to list of tweet_id_str, 
        # which uniquely define the tweets that the bot has already made
        # during the day. List is cleared at the end of every day
        self.map_bot_already_tweeted = { bot_id:[] for bot_id in range(0,4+1) }
        
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
            f = open("%s/records_%d.csv" % (self.path, bot_id), "a")
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

    def delete_last_tweet(self, all=1, bot_id=0):
        for id in range(0, 4+1):
            if all or (all == 0 and id == bot_id):
                timeline = self.bots[id].get_timeline("ml%d_gt" % (id+1), n=1)
                for tweet in timeline:
                    self.bots[id].api.destroy_status(tweet.id)

        
    def populate_source(self, filename):
        f = open(filename, 'r')
        lines = f.readlines()
        f.close()
        for line in lines:
            self.list_source.append( line.strip() )
  

    def follow(self, sourcefile, followingfile, randomize=0):
        """
        Each bot follows 1/5 of the people in sourcefile
        Argument
        sourcefile - each line is a user_id_string
        followingfile - each line is a user_id already followed by a bot
        """

        f = open(followingfile, 'r')
        list_already_followed = f.readlines()
        f.close()

        f = open(sourcefile, 'r')
        list_ids = f.readlines()
        f.close()
        num_ids = len(list_ids)
        
        if randomize:
            # Randomize the list
            for idx in range(0, num_ids-1):
                temp = list_ids[idx]
                # Pick random index from the rest of the list
                random_idx = random.randint(idx+1, num_ids-1)
                # Swap
                list_ids[idx] = list_ids[random_idx]
                list_ids[random_idx] = temp

        # Limit is max 5000 friends per bot. Use 1000 for safety
        # Limit on how many more people can be followed by each bot
        list_limit = [0 for bot_id in range(0,5)]
        for bot_id in range(0, 5):
            list_limit[bot_id] = 1000 - self.bots[bot_id].user.friends_count

        # Counter for each bot
        list_count = [0 for bot_id in range(0, 5)]
        idx = 0
        while idx < num_ids-4:
            if list_count == list_limit:
                break
            # File to write the all the new people being followed
            f = open('list_new_friends.txt','a')
            for bot_id in range(0, 5):
                # Skip over bot if already reached limit
                if list_count[bot_id] > list_limit[bot_id]:
                    continue
                uid = list_ids[idx+bot_id]
                if uid not in list_already_followed:
                    print "%d: Bot %d is following %s" % (idx+bot_id, bot_id, uid.strip())
                    error_code = self.bots[bot_id].follow(uid.strip())
                    list_count[bot_id] += 1
                    f.write(uid)
                    if error_code == 1:
                        f.close()
                        return
            f.close()
            print "Sleep for 15min"
            time.sleep(15*60)
            idx += 5


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
        
    
    def choose_tweet(self, bot_id):
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
        list_first_person = ["we", "we've", "we'll", "we're", "our", "me", 
                             "my", "mine", "us", "i", "i'll", "i'm", "i've"]

        # List of sources, each of which will get eliminated
        # if all of its most recent 5 tweets are not suitable for posting
        # by bot
        list_options_source = range(0, len(self.list_source))

        while not done:

            # If all sources have been exhausted without finding a suitable tweet
            if list_options_source == []:
                done = 1
                return "", ""

            # Randomly choose a source from remaining options
            idx_source = random.choice( list_options_source )
            source_name = self.list_source[idx_source]
            # Get the 5 most recent posts by the source
            if "#" in source_name:
                source_timeline = self.bots[bot_id].get_by_hashtag(source_name, 5)
            else:
                source_timeline = self.bots[bot_id].get_timeline(source_name, 5)
    
            num = len(source_timeline)
            done_inner = 0
            # List of potential tweets, each of which will get eliminated
            # if it is not suitable for posting by the bot
            list_options_timeline = range(0, num)

            while not done_inner:
    
                # List of options is guaranteeed to decrease by 1 each iteration,
                # so while loop will terminate once it is empty                
                if list_options_timeline == []:
                    done_inner = 1
                    # This particular source has been exhausted
                    list_options_source.remove(idx_source)
                    continue

                # Randomly choose a tweet from remaining options and remove
                # this option
                idx_tweet = random.choice( list_options_timeline )
                list_options_timeline.remove(idx_tweet)

                text = source_timeline[idx_tweet].text
                tweet_id_str = source_timeline[idx_tweet].id_str

                # Do not duplicate a post
                if tweet_id_str in self.map_bot_already_tweeted[bot_id]:
                    continue
                else:
                    list_token = text.lower().split()
                    violate = 0
                    # Check for violation of the first-person pronoun rule
                    for word in list_first_person:
                        if word in list_token:
                            violate = 1
                            break
                    # Violation occurs if tweet is a "reply" (e.g. "Blah @someone blah")
                    if ( ('RT @' not in text) and ('@' in text) ):
                        violate = 1
                    if violate == 0:
                        # If no violation was found, return this tweet
                        done_inner = 1
                        self.map_bot_already_tweeted[bot_id].append(tweet_id_str)
                        if ( 'RT @' in text ): # If tweet is a retweet, get the original tweet
                            try:
                                text = source_timeline[idx_tweet].retweeted_status.text
                            except:
                                pass
                        return text, source_name


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
        id_str of the tweet made by bot, or "" if unsuccessful
        """
        
        text, source_name = self.choose_tweet(bot_id)
        
        # If could not find a suitable tweet, do not act
        if text == "":
            return ""

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
        success = self.bots[bot_id].tweet(text)
        # If tweet was unsuccessful, then skip over rest of function
        if not success:
            return ""

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
            try:
                id_str_mine = self.bots[bot_id].get_timeline(self.bots[bot_id].name, n=1)[0].id_str
            except Exception as e:
                print "Bot %d: unexplainable error " % bot_id, e
                id_str_mine = id_str_prev
                break
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
            print "%s : %s" % (source_name, text.encode('utf8'))
    
        # Store tweet_id and time of tweet into the queue of actions that still
        # require recording of response
        self.map_bot_tweet_prev[bot_id].put([id_str_mine, time_of_tweet])
        return id_str_mine
    
       
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
        f = open("%s/records_%d.csv" % (self.path, bot_id), "a")
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
        f = open("%s/retweeters_%d.csv" % (self.path, bot_id), "a")
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
        f = open("%s/likers_%d.csv" % (self.path, bot_id), "a")
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

        f = open("%s/matrix_day%d.csv" % (self.path, day), "a")
        # Write header
        s = ","
        for id_str in list_followers:
            s += "%s," % id_str
        s += "\n"
        f.write(s)

        # Counter for get_friends() rate limit
        counter_friends = 0
        # Bot to use for get_friends(). Cyclic
        bot_id_friends = 0

        # Write rows of matrix
        for id_str in list_followers:
            # Get friends of this person
            # list_friend = self.observer.get_friends(id_str)
            list_friend = self.bots[bot_id_friends].get_friends(id_str)

            # Check whether need to switch to another bot
            counter_friends += 1
            if counter_friends == 15:
                bot_id_friends = (bot_id_friends + 1) % 6 # go to next bot
                counter_friends = 0 # reset counter

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


    def observe_follower_detail(self, list_to_track, map_follower_lasttweet):
        """
        This function is called only at the end of a day, after event_queue has been emptied
        For each follower, append to three files:
        1. records_*.csv - tweet_id, time created, num likes, num retweets, num followers
        2. likers_*.csv - tweet_id, liker_1_id, ... , liker_n_id
        3. retweeters_*.csv - tweet_id, retweeter_1_id, time_1, ... , retweeter_n_id, time_n

        Argument
        1. list_to_track - the list of followers (refreshed at start of every day)
        2. map_follower_lasttweet - map from follower_id_str to id_str of the most recent post
        as recorded at the start of the day
        """

        num_posts = 0 # count the total actions taken by all followers
        accum = 0 # running sum of number of tweets
        counter = 0 # print running sum for at every multiple of 50
        # Map from follower_id to count of how many tweets they made
        # For diagnosing which follower is responsible for having too many tweets
        # and making the program take too long
        map_follower_count = {} 

        for follower_id in list_to_track:
            last_tweet = map_follower_lasttweet[follower_id]
            if last_tweet != '':
                tweets = self.observer.get_timeline_since(follower_id, since=last_tweet)
            else:
                tweets = self.observer.get_timeline(follower_id, verbose=0)            

            num_posts += len(tweets)

            # Write to records_*.csv
            path_to_file = "%s/records_%s.csv" % (self.path, follower_id)
            if os.path.isfile(path_to_file):
                f = open(path_to_file, "a")
            else: # if file did not exist previously, write header
                f = open(path_to_file, "a")
                f.write("tweet_id_str,time,text,num_like,num_retweet\n")
            for tweet in tweets[::-1]:
                # creation_time = tweet.created_at.strftime('%Y-%m-%d %H:%M:%S')
                # The following line, not the previous line, is the correct EST datetime
                creation_time = (tweet.created_at + 
                                 datetime.timedelta(hours=-4)).strftime('%Y-%m-%d-%H:%M:%S')
                text_mod = tweet.text.replace("\n", " ") # remove newlines
                s = "%s,%s,%s,%d,%d\n" % (tweet.id_str, creation_time, text_mod, tweet.favorite_count, tweet.retweet_count)
                f.write(s.encode('utf8'))
            f.close()

            list_tweet_id = [tweet.id_str for tweet in tweets]
            
            # Diagnosis
            map_follower_count[follower_id] = len(list_tweet_id)
            accum += len(list_tweet_id)
            counter += 1
            if counter % 50 == 0:
                culprit = max(map_follower_count.iteritems(), key=itemgetter(1))[0]
                num = max(map_follower_count.iteritems(), key=itemgetter(1))[1]
                print "observe_follower_detail() counter %d, accum %d" % (counter, accum)
                print "Max: follower %s has %d tweets" % (culprit, num)
            
            # Write to likers_*.csv
            f = open("%s/likers_%s.csv" % (self.path, follower_id), "a")
            for tweet_id_str in list_tweet_id[::-1]:
                s = "%s," % tweet_id_str
                list_liker = self.observer.get_likers(tweet_id_str)
                s = s + ",".join(list_liker)
                s += "\n"
                f.write(s)
            f.close()

            map_tweet_retweeter = self.observer.get_retweets( list_tweet_id )
            f = open("%s/retweeters_%s.csv" % (self.path, follower_id), "a")
            # Write to retweeters_*.csv
            for tweet_id_str, list_retweeter_info in map_tweet_retweeter.iteritems():
                s = "%s," % tweet_id_str
                for retweeter in list_retweeter_info:
                    retweeter_id_str = retweeter[0]
                    retweeter_datetime = retweeter[1].strftime('%Y-%m-%d-%H-%M-%S')
                    s += "%s,%s," % (retweeter_id_str, retweeter_datetime)
                s += "\n"
                f.write(s)
            f.close()

        f = open(self.logfilename, "a")
        f.write("Total activity by followers: %d\n" % num_posts)
        f.close()        


    def observe_follower_friend_detail(self, list_to_track, map_follower_map_friend_lasttweet):
        """
        This function is called only at the end of a day, after event_queue has been emptied
        For each follower, append to file:
        records_*.csv - friend_id, tweet_id, time created, num likes, num retweets, num followers

        Argument
        1. list_to_track - the list of followers (refreshed at start of every day)
        2. map_follower_map_friend_lasttweet - map from follower_id_str to map from 
        friend_id_str to id_str of the most recent post as recorded at the start of the day
        """
        # Counter for get_timeline() rate limit
        counter_timeline = 0
        # Bot to use for get_timeline(). Cyclic
        bot_id_timeline = 0

        # For each follower of bot
        for follower_id in list_to_track:
            # Extract the map from friend_id --> tweet_id
            map_friend_lasttweet = map_follower_map_friend_lasttweet[follower_id]
            
            # Open friends_of_*.csv for appending
            path_to_file = "%s/friends_of_%s.csv" % (self.path, follower_id)
            if os.path.isfile(path_to_file):
                f = open(path_to_file, "a")
            else: # if file did not exist previously, write header
                f = open(path_to_file, "a")
                f.write("friend_id,tweet_id,time,text,num_like,num_retweet,num_posts\n")

            # For each friend and their respective last tweet
            for friend_id_str, tweet_id_str in map_friend_lasttweet.iteritems():
                # Get all new tweets since the last tweet
                if tweet_id_str != '':
                    # tweets = self.observer.get_timeline_since(friend_id_str, since=tweet_id_str)
                    tweets = self.bots[bot_id_timeline].get_timeline_since(friend_id_str, since=tweet_id_str)
                else:
                    # tweets = self.observer.get_timeline(follower_id, verbose=0)
                    tweets = self.bots[bot_id_timeline].get_timeline(friend_id_str, verbose=0)

                # Check whether need to switch to another bot for get_timeline
                counter_timeline += 1
                if counter_timeline == 180:
                    bot_id_timeline = (bot_id_timeline + 1) % 6 # go to next bot
                    counter_timeline = 0 # reset counter

                num_posts = len(tweets)

                # Record details of each tweet made during the day
                for tweet in tweets[::-1]:
                    creation_time = (tweet.created_at + 
                                     datetime.timedelta(hours=-4)).strftime('%Y-%m-%d-%H:%M:%S')
                    text_mod = tweet.text.replace("\n", " ") # remove newlines
                    s = "%s,%s,%s,%s,%d,%d,%d\n" % (friend_id_str, tweet.id_str, creation_time, text_mod,
                                                 tweet.favorite_count, tweet.retweet_count, num_posts)
                    f.write(s.encode('utf8'))
                    
            f.close()            

    def reservoir_sample(self, input_list, N):
        """
        Returns list of N randomly sampled points from input_list
        """
        sample = []
        # Single pass through list
        for idx, element in enumerate(input_list):
            if idx < N:
                sample.append(element)
            elif idx >= N and random.random() < N / float(idx+1):
                replace = random.randint(0, len(sample)-1)
                sample[replace] = element
        return sample

    def initialize_maps(self, list_to_track):
        """
        This function is called at the start of every day (usually sometime between 12midnight-1am)
        Takes in list_to_track, which is the list of all followers of the bots
        Returns two maps:
        1. map_follower_lasttweet - map from follower_id to tweet_id of most recent tweet
        2. map_follower_map_friend_lasttweet - map from follower_id to map from friend_id
        to tweet_id of most recent tweet by that friend of that follower
        """
        # Map from follower_id_str --> id_str of last post
        map_follower_lasttweet = {}
        # Map from follower_id_str --> map from friend_id_str --> id_str of last post
        map_follower_map_friend_lasttweet = {}
        # Counter for get_timeline() rate limit
        counter_timeline = 0
        # Bot to use for get_timeline(). Cyclic
        bot_id_timeline = 0
        # Counter for get_friends() rate limit
        counter_friends = 0
        # Bot to use for get_friends(). Cyclic
        bot_id_friends = 0

        for follower_id_str in list_to_track:
            # Get the most recent post by follower_id_str
            # tweet_list = self.observer.get_timeline(follower_id_str, n=1, verbose=0)
            tweet_list = self.bots[bot_id_timeline].get_timeline(follower_id_str, n=1)

            # Store most recent post by follower_id_str, if post exists
            if len(tweet_list) != 0:
                map_follower_lasttweet[follower_id_str] = tweet_list[0].id_str
            else:
                map_follower_lasttweet[follower_id_str] = ''

            # Check whether need to switch to another bot for get_timeline
            counter_timeline += 1
            if counter_timeline == 180:
                bot_id_timeline = (bot_id_timeline + 1) % 6 # go to next bot
                counter_timeline = 0 # reset counter

            # Get list of all friends of follower_id_str
            # list_friends = self.observer.get_friends(follower_id_str)
            list_friends = self.bots[bot_id_friends].get_friends(follower_id_str)
            if len(list_friends) > 50:
                list_friends = self.reservoir_sample(list_friends, 50)

            # Check whether need to switch to another bot
            counter_friends += 1
            if counter_friends == 15:
                bot_id_friends = (bot_id_friends + 1) % 6 # go to next bot
                counter_friends = 0 # reset counter

            # Map from friend_id_str --> id_str of last post
            map_friend_lasttweet = {}
            for friend_id_str in list_friends:
                # tweet_list = self.observer.get_timeline(friend_id_str, n=1, verbose=0)
                tweet_list = self.bots[bot_id_timeline].get_timeline(friend_id_str, n=1)
                if len(tweet_list) != 0:
                    map_friend_lasttweet[friend_id_str] = tweet_list[0].id_str
                else:
                    map_friend_lasttweet[friend_id_str] = ''
                counter_timeline += 1
                if counter_timeline == 180:
                    bot_id_timeline = (bot_id_timeline + 1) % 6 # go to next bot
                    counter_timeline = 0 # reset counter

            map_follower_map_friend_lasttweet[follower_id_str] = map_friend_lasttweet

        return map_follower_lasttweet, map_follower_map_friend_lasttweet


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

        num_day = start_day_num
        # Each iteration of this loop is a day
        while num_day < total_day:
        
            num_day += 1
            f = open(self.logfilename, "a")
            f.write("\nDay %d\n" % num_day)
            f.close()
            print "Day %d" % num_day
        
            # Reset number of posts made during day
            num_post = 0

            # At start of this day, update the set of people to track
            self.observer.update_tracking( ['ml%d_gt' % idx for idx in range(1,5+1)] )
            list_to_track = list(self.observer.tracking)
            list_to_track.sort()

            map_follower_lasttweet, map_follower_map_friend_lasttweet = self.initialize_maps(list_to_track)

            now = datetime.datetime.now()
        
            # At the start of each day, generate the entire set of action times
            # for all bots
            self.generate_post_time_random( (8,0,0), (23,0,0), 5 )
            # self.generate_post_time_random( (8,0,0), (22,30,0), 1 )

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
                    id_str_mine = self.act(event_bot, attribute=0, verbose=1)
                    if id_str_mine != "":
                        num_post += 1
                        t_observe = (23,30,num_post)
                        # Insert the observation event into the queue
                        self.event_queue.put( (t_observe, event_bot, 'o') )
                elif event_type == 'o': # If event is an observation of response
                    self.record(event_bot)
                    
            # Sleep until 00:00:10 of next day
            current_time = datetime.datetime.now()
            sec_until_tomorrow = 24*3600 - (current_time.hour*3600 + current_time.minute*60 \
                                            + current_time.second)                                            
            print "Sleep for %d seconds until tomorrow" % sec_until_tomorrow
            time.sleep(sec_until_tomorrow + 10)
            
            # Record connectivity matrix
            self.record_network(list_to_track, num_day)
                        
            # Record follower details
            self.observe_follower_detail(list_to_track, map_follower_lasttweet)

            # Record follower's friends details
            self.observe_follower_friend_detail(list_to_track, map_follower_map_friend_lasttweet)

            # Clear the list of tweets made by each bot during previous day
            self.map_bot_already_tweeted = { bot_id:[] for bot_id in range(0,4+1) }           


if __name__ == "__main__":
    
    exp = main(init_bots=1, init_observer=1)
