# -*- coding: utf-8 -*-
"""
Created on Thu Sep 15 12:32:08 2016

@author: jiachen.yang@gatech.edu
"""

import rlbot
import process

import time
import random
import datetime
from operator import itemgetter
import Queue
import os


class experiment:

    def __init__(self, init_bots=1, init_observer=1, extra_observers=0, 
                 sourcefile='source.txt', logfile='log.txt'):
        
        # self.path = '/home/t3500/devdata/rlbot_data'
        # self.path = '/home/t3500/devdata/rlbot_data_course'
        # self.path = '/home/t3500/devdata/rlbot_data_highfrequency'
        # self.path = '/home/t3500/devdata/rlbot_data_secondorder' # here
        self.path = '/home/t3500/devdata/rlbot_data_experiment2'
        # self.path = r'C:\Users\Jiachen\Documents\Projects\CS8903\rlbot_twitter' # here
        self.logfilename = self.path + '/' + logfile

        # List of bots
        self.bots = []
        if init_bots:
            for idx in range(1, 5+1):
                self.bots.append( rlbot.rlbot(name="ml%d_gt"%idx, 
                                              keyfile="key_bot%d.txt"%idx) )
        
        if init_observer:
            self.observer = rlbot.rlbot('matt_learner', 'key_ml.txt')

        if extra_observers:
            self.observer2 = rlbot.rlbot('username124816', 'keys.txt')
            self.observer3 = rlbot.rlbot('username124816', 'keys2.txt')
            
        if init_bots and init_observer:
            self.bots.append( self.observer )

        if init_bots and init_observer and extra_observers:
            self.bots.append( self.observer2 )
            self.bots.append( self.observer3 )

        # List of times to observe activity of followers
        # This is independent of the observations made by each bot
        # Each bot is responsible for observing the response to its own tweets
        self.observation_time = []
        # self.generate_observation_time( (0,30,0), (23,30,0), 23 )

        # Map from bot_id to Queue of tweet id_str by that bot
        # Each element in the queue is the id_str of a tweet made earlier, that 
        # still requires a measurement of the response
        self.map_bot_tweet_prev = { idx:Queue.Queue() for idx in range(0,4+1) }
        
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
        self.record_queue = Queue.PriorityQueue(maxsize=-1)

        # Map from bot_id --> list of times when that bot is supposed to post
        self.map_bot_action_time = { idx:[] for idx in range(0,4+1)}

        # List of recorded tuples, to be sorted chronologically after recording
        # of response to bots has finished
        self.list_response_tuples = []
        self.num_response_outsiders = 0 # number of retweets by people not inside network
        # For checking whether a retweeter is inside the network
        self.p = process.process(1)
        # Populate mapping from userid of follower to anonymized unique label
        self.p.read_map_file() 

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
  

    def unfollow(self, bot_id, num):
        """
        From bot's list of friends, randomly select num of them and unfollow
        Argument:
        bot_id - 0 to 4
        num - number of friends to select and unfollow
        """
        list_friends = self.bots[bot_id].get_friends('ml%d_gt' % (bot_id + 1))
        num_friends_initial = len(list_friends)
        if num > len(list_friends):
            print "ml%d_gt only has %d friends. Cannot unfollow %d people" % (bot_id+1, num_friends_initial, num)
        else:
            list_to_unfollow = self.reservoir_sample(list_friends, num)
            for friend_id in list_to_unfollow:
                try:
                    self.bots[bot_id].api.destroy_friendship(friend_id)
                except Exception as err:
                    print err
            

    def follow(self, sourcefile, target=550, randomize=0):
        """
        Each bot follows 1/5 of the people in sourcefile
        Argument
        sourcefile - each line is a user_id_string
        """

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

        # Limit is max 5000 friends per bot. Use 2000 for safety
        # Limit on how many more people can be followed by each bot
        list_limit = [0 for bot_id in range(0,5)]
        for bot_id in range(0, 5):
            list_limit[bot_id] = 2000 - self.bots[bot_id].user.friends_count

        # Counter for each bot
        list_count = [0 for bot_id in range(0, 5)]
        # 1 at index i indicates that bot i has enough followers
        list_done = [0 for bot_id in range(0, 5)] 
        idx = 0
        while idx < num_ids:
            if list_count == list_limit:
                break
            if sum(list_done) == 5: # all five bots have enough followers
                break
            # File to write the all the new people being followed
            f = open('list_new_friends.txt','a')
            for bot_id in range(0,5):
                followers_count = self.bots[bot_id].api.get_user('ml%d_gt' % (bot_id+1)).followers_count
                if followers_count >= target:
                    # Skip over bot if already has enough followers
                    print "Bot %d already has %d followers" % (bot_id, followers_count)
                    list_done[bot_id] = 1
                    continue
                if list_count[bot_id] > list_limit[bot_id]:
                    # Skip over bot if already reached limit
                    print "Bot %d reached limit" % (bot_id)
                    continue
                uid = list_ids[idx]
                print "%d: Bot %d is following %s" % (idx, bot_id, uid.strip())
                idx += 1
                error_code = self.bots[bot_id].follow(uid.strip())
                list_count[bot_id] += 1
                f.write(uid)
                if error_code == 1:
                    f.close()
                    return
            f.close()
            print "Sleep for 8min"
            time.sleep(8*60)


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
            idx = input_text.find(":")
            if idx == -1:
                # Doesn't match format of retweet, so just return original
                return input_text
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
        # Record into activity_stage*.txt
        epoch = datetime.datetime.utcfromtimestamp(0)
        dt_utc = datetime.datetime.utcnow()
        seconds = (dt_utc - epoch).total_seconds()
        self.list_response_tuples.append( (seconds, bot_id+1, bot_id+1) )

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
        epoch = datetime.datetime.utcfromtimestamp(0)
        
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
        # tweet id_str, retweeter1 id_str, datetime1, retweeter2 id_str, datetime2,...
        list_retweeter_info = self.observe_retweeter(bot_id, tweet_id_str)
        s = "%s," % tweet_id_str
        for retweeter in list_retweeter_info:
            retweeter_id_str = retweeter[0]
            retweeter_datetime = retweeter[1].strftime('%Y-%m-%d-%H-%M-%S')
            s += "%s,%s," % (retweeter_id_str, retweeter_datetime)
            # new
            # If retweeter is inside the network of followers
            if retweeter_id_str in self.p.map_userid_number:
                retweeter_num = self.p.map_userid_number[retweeter_id_str]
                dt_utc = retweeter[1] + datetime.timedelta(hours=4)
                seconds = (dt_utc - epoch).total_seconds()
                self.list_response_tuples.append( (seconds, retweeter_num, bot_id+1) )
            else:
                self.num_response_outsiders += 1
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


    def generate_post_time(self, phase):
        """
        Prompts for file name to proceed
        Assumes that file is located in same folder as this program
        Assumes that file has format
        t_11 t_12 ...
        t_21 t_22 t_23 ...
        ...
        t_51 t_52 ...
        where t_{ij} is the j-th time in seconds since either 8am or 8pm
        when bot i should post
        Populates self.map_bot_action_time
        """
        file_name = raw_input("Enter name of time file: ")
        f = open(file_name, 'r')
        lines = f.readlines()
        f.close()
        
        f = open(self.logfilename, "a")
        for bot_id in range(5):
            f.write("Bot %d tweet times\n" % bot_id) # write to log file
            # List of integers, each integer is the number of seconds since 00:00:00
            list_times = lines[bot_id].strip().split(' ')

            for idx in range(len(list_times)):
                t_sec = int(list_times[idx])
                if phase == 'day':
                    # Offset from 8am
                    t_sec += 8*3600
                elif phase == 'night':
                    t_sec += 20*3600
                minute, second = divmod(t_sec, 60)
                hour, minute = divmod(minute, 60) # hour may exceed 23
                # Replace time in seconds with tuple
                list_times[idx] = (hour, minute, second)
                f.write("%d,%d,%d\n" % (hour, minute, second))

            # Sort into chronological order and store into map   
            list_times.sort()
            print "Bot %d" % bot_id
            print list_times
            self.map_bot_action_time[bot_id] = list_times

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


#    def record_network(self, list_followers, day):
#        """
#        Run once per day. Creates the connection matrix A for the set of followers
#        of the bot. A_ij = 1 iff follower_i follows follower_j
#        Stores results in matrix_day*.csv
#        """
#        print "Inside record_network() at ", datetime.datetime.now()
#        # Create map from follower ID to index for efficiency
#        map_id_index = {}
#        count = len(list_followers)
#        for index in range(0, count):
#            map_id_index[ list_followers[index] ] = index
#
#        f = open("%s/matrix_day%d.csv" % (self.path, day), "a")
#        # Write header
#        s = ","
#        for id_str in list_followers:
#            s += "%s," % id_str
#        s += "\n"
#        f.write(s)
#
#        # Counter for get_friends() rate limit
#        counter_friends = 0
#        # Bot to use for get_friends(). Cyclic
#        bot_id_friends = 0
#
#        # Write rows of matrix
#        for id_str in list_followers:
#            # Get friends of this person
#            list_friend = self.bots[bot_id_friends].get_friends(id_str)
#
#            # Check whether need to switch to another bot
#            counter_friends += 1
#            if counter_friends == 15:
#                bot_id_friends = (bot_id_friends + 1) % 6 # go to next bot
#                counter_friends = 0 # reset counter
#
#            # Create row A_i, where A_ij = 1 iff the person with
#            # id_str follows the person at column index j
#            temp = [0 for x in range(0, count)]
#            for friend_id in list_friend:
#                if friend_id in map_id_index:
#                    temp[ map_id_index[friend_id] ] = 1
#            s = ','.join(map(str, temp))
#            s = id_str + ',' + s + '\n'
#            f.write(s)
#
#        f.close()

    def record_network(self, map_follower_list_friends, day):
        """
        Run once per day. Creates the connection matrix A for the set of followers
        of the bot. A_ij = 1 iff follower_i follows follower_j

        Argument:
        map_follower_list_friends - map from follower_id to list of friends
        of that follower. This map was already computed by initialize_maps()
        day - number of day 

        Stores results in matrix_day*.csv
        """
        print "Inside record_network() at ", datetime.datetime.now()
        list_followers = map_follower_list_friends.keys()
        # Create map from follower ID to index for efficiency
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

        # Write rows of matrix
        for id_str in list_followers:
            # Get friends of this person
            # list_friend = self.bots[bot_id_friends].get_friends(id_str)
            list_friends = map_follower_list_friends[id_str]
            # list_friend = map_follower_map_friend_lasttweet[id_str].keys()

            # Create row A_i, where A_ij = 1 iff the person with
            # id_str follows the person at column index j
            temp = [0 for x in range(0, count)]
            for friend_id in list_friends:
                if friend_id in map_id_index:
                    # If the friend is among the set of followers
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
        print "Inside observe_follower_detail() at ", datetime.datetime.now()
        num_posts = 0 # count the total actions taken by all followers

        # For diagnosis
        counter = 0 # print running sum for at every multiple of 50
        count_max = 0
        culprit = ''

        # Counter for get_retweets() rate limit
        counter_retweets = 0
        # Bot to use for get_retweets(). Cyclic
        bot_id_retweets = 0

        for follower_id in list_to_track:
            last_tweet = map_follower_lasttweet[follower_id]
            if last_tweet != '':
                tweets = self.observer.get_timeline_since(follower_id, since=last_tweet)
            else:
                tweets = self.observer.get_timeline(follower_id, verbose=0)            

            num_posts += len(tweets)

            # Diagnosis
            temp = len(tweets)
            if temp > count_max:
                count_max = temp
                culprit = follower_id
            counter += 1
            if counter % 50 == 0:
                print "observe_follower_detail() counter %d, num_posts %d" % (counter, num_posts)
                print "Max: follower %s has %d tweets" % (culprit, count_max)

            # Write to records_*.csv
            path_to_file = "%s/records_%s.csv" % (self.path, follower_id)
            if os.path.isfile(path_to_file):
                f = open(path_to_file, "a")
            else: # if file did not exist previously, write header
                f = open(path_to_file, "a")
                f.write("tweet_id_str,time,text,num_like,num_retweet\n")
            for tweet in tweets[::-1]:
                # tweet.created_at returns UTC time, which is 4 hours ahead of EST
                creation_time = (tweet.created_at + 
                                 datetime.timedelta(hours=-4)).strftime('%Y-%m-%d-%H:%M:%S')
                text_mod = tweet.text.replace("\n", " ") # remove newlines
                s = "%s,%s,%s,%d,%d\n" % (tweet.id_str, creation_time, text_mod, tweet.favorite_count, tweet.retweet_count)
                f.write(s.encode('utf8'))
            f.close()

            # Ignore potential bots and spammers that post with high frequency
            if len(tweets) > 3:
                tweets = self.reservoir_sample(tweets, 3)

            list_tweet_id = [tweet.id_str for tweet in tweets]
            
            # Write to likers_*.csv
            f = open("%s/likers_%s.csv" % (self.path, follower_id), "a")
            for tweet_id_str in list_tweet_id[::-1]:
                s = "%s," % tweet_id_str
                list_liker = self.observer.get_likers(tweet_id_str)
                s = s + ",".join(list_liker)
                s += "\n"
                f.write(s)
            f.close()

            # map_tweet_retweeter = self.observer.get_retweets( list_tweet_id )
            # Write to retweeters_*.csv
            f = open("%s/retweeters_%s.csv" % (self.path, follower_id), "a")
            for tweet_id_str in list_tweet_id:
                # Bottleneck: with 1950 followers, assuming each makes 3 tweets per day
                # and each of the 8 bots can observe 75 retweets per 15 min, this takes
                # 1950 * 3 / (75*8) / 4 = 2.4 hours
                list_tuples = self.bots[bot_id_retweets].get_retweets_single(tweet_id_str, verbose=0)

                # Check whether need to switch to another bot for get_retweets_single()
                counter_retweets += 1
                if counter_retweets == 75:
                    bot_id_retweets = (bot_id_retweets + 1) % len(self.bots) # go to next bot
                    counter_retweets = 0 # reset counter

                s = "%s," % tweet_id_str
                for pair in list_tuples:
                    retweeter_id_str = pair[0]
                    retweeter_datetime = pair[1].strftime('%Y-%m-%d-%H-%M-%S')
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
        friends_of_*.csv - friend_id, tweet_id, time created, num likes, num retweets, num followers

        Argument
        1. list_to_track - the list of followers (refreshed at start of every day)
        2. map_follower_map_friend_lasttweet - map from follower_id_str to map from 
        friend_id_str to id_str of the most recent post as recorded at the start of the day
        """
        print "Inside observe_follower_friend_detail() at ", datetime.datetime.now()
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
                if counter_timeline == 800:
                    bot_id_timeline = (bot_id_timeline + 1) % len(self.bots) # go to next bot
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
        This function is called at the start of every day
        Takes in list_to_track, which is the list of all followers of the bots
        Returns three maps:
        1. map_follower_lasttweet - map from follower_id to tweet_id of most recent tweet
        2. map_follower_map_friend_lasttweet - map from follower_id to map from friend_id
        to tweet_id of most recent tweet by that friend of that follower
        3. map_follower_list_friends - map from follower_id to list of friends of that 
        follower
        """
        print "Inside initialize_maps() at ", datetime.datetime.now()
        # Map from follower_id_str --> id_str of last post
        map_follower_lasttweet = {}
        # Map from follower_id_str --> map from friend_id_str --> id_str of last post
        map_follower_map_friend_lasttweet = {}
        # Map from follower_id_str --> list of friend_id_str
        map_follower_list_friends = {}
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
            tweet_list = self.bots[bot_id_timeline].get_timeline(follower_id_str, n=1)

            # Store most recent post by follower_id_str, if post exists
            if len(tweet_list) != 0:
                map_follower_lasttweet[follower_id_str] = tweet_list[0].id_str
            else:
                map_follower_lasttweet[follower_id_str] = ''

            # Check whether need to switch to another bot for get_timeline
            counter_timeline += 1
            if counter_timeline == 180:
                # go to next bot
                bot_id_timeline = (bot_id_timeline + 1) % len(self.bots) 
                counter_timeline = 0 # reset counter

            # Get list of all friends of follower_id_str
            # Bottleneck: With 1950 followers, cycling through 8 bots
            # with each bot allowed 15 calls of get_friends() per 15min, this takes
            # 1950 / (8*15) / 4 = 4 hours
            list_friends = self.bots[bot_id_friends].get_friends(follower_id_str)
            map_follower_list_friends[follower_id_str] = list_friends
            if len(list_friends) > 10:
                list_friends = self.reservoir_sample(list_friends, 10)

            # Check whether need to switch to another bot
            counter_friends += 1
            if counter_friends == 15:
                # go to next bot
                bot_id_friends = (bot_id_friends + 1) % len(self.bots) 
                counter_friends = 0 # reset counter

            # Map from friend_id_str --> id_str of last post
            map_friend_lasttweet = {}
            for friend_id_str in list_friends:
                tweet_list = self.bots[bot_id_timeline].get_timeline(friend_id_str, n=1)
                if len(tweet_list) != 0:
                    map_friend_lasttweet[friend_id_str] = tweet_list[0].id_str
                else:
                    map_friend_lasttweet[friend_id_str] = ''
                # Check whether need to switch to another bot
                counter_timeline += 1
                if counter_timeline == 180:
                    # go to next bot
                    bot_id_timeline = (bot_id_timeline + 1) % len(self.bots) 
                    counter_timeline = 0 # reset counter

            map_follower_map_friend_lasttweet[follower_id_str] = map_friend_lasttweet

        print "Exiting initialize_maps() at ", datetime.datetime.now()
        return map_follower_lasttweet, map_follower_map_friend_lasttweet, map_follower_list_friends


    def run(self, total_stage, start_stage_num=0, initial_phase='night', comp=2, header=0):
        """
        Main program that schedules and executes all events for the entire
        duration of the experiment
        
        Argument:
        1. total_stage - total number of days to run the system
        2. start_stage_num - 0 if running the program from day 0 (ensure that log folder
        is cleared), nonzero if need to restart the program after any number of days 
        has already elapsed.
        3. header - 1 to write headers in records_*.csv
        """        
        if header:
            self.write_headers()

        num_stage = start_stage_num
        phase = initial_phase
        # Each iteration of this loop is a stage
        while num_stage < total_stage:
        
            num_stage += 1
            f = open(self.logfilename, "a")
            f.write("\nStage %d comp %d, %s\n" % (num_stage, comp, phase))
            f.close()
            print "Stage %d, phase %s at" % (num_stage, phase), datetime.datetime.now()
        
            # Reset number of posts made during stage
            num_post = 0

            # At start of this stage, update the set of people to track,
            # which comprises all followers of the five bots
            self.observer.update_tracking( ['ml%d_gt' % idx for idx in range(1,5+1)] )
            list_to_track = list(self.observer.tracking)
            list_to_track.sort()

            # Generates mappings to store the latest tweets by all followers and friends
            # of followers. Will be used at end of day as reference point to
            # find all new tweets made by these people during the day
            # map_follower_lasttweet, map_follower_map_friend_lasttweet, map_follower_list_friends = self.initialize_maps(list_to_track) # commented
        
            # At the start of each stage, generate the entire set of action times
            # for all bots
            # self.generate_post_time_random( (8,0,0), (23,0,0), 5 ) # old # here
            self.generate_post_time(phase) # new # here

            now = datetime.datetime.now()

            # Store all action times into priority queue
            # For each action time, include information on which bot is associated
            # with the time, and indicate that the event type is action 'a'
            for bot_id in range(0, 4+1):
                list_time = self.map_bot_action_time[bot_id]
                for t_action in list_time:
                    if self.is_after_now( now, t_action ):
                        self.event_queue.put( (t_action, bot_id, 'a') )
                    else:
                        self.event_queue.put( (t_action, bot_id, 'a') )
                        f = open(self.logfilename, 'a')
                        f.write("\nERROR: desired post time occurs before current time\n")
                        f.close()
                        print "ERROR: desired post time occurs before current time", t_action
        
            # While there are remaining action events for this stage
            while self.event_queue.qsize():
    
                event = self.event_queue.get()
                event_time = event[0]
                event_bot = event[1]
                event_type = event[2]
                
                # Get current time
                now = datetime.datetime.now()
                if phase == 'day' or (phase == 'night' and event_time[0] < 24):
                    # For the case phase == 'night', event_time[0] may be greater than 24
                    # to represent event occurring between 12midnight and 7:30am
                    # Since event_time[0] is less than 24, that means event occurs
                    # between 8pm and 12midnight. Treat it like the 'day' case.
                    # Seconds elapsed since the start of the day at midnight
                    now_seconds = 3600*now.hour + 60*now.minute + now.second
                    event_time_seconds = 3600*event_time[0] + 60*event_time[1] + event_time[2]
                else:
                    # Enter here when phase == 'night' and event_time[0]>=24, meaning
                    # next event needs to happen between midnight and 7:30am of next day
                    if now.hour >= 20: # meaning still not past midnight
                        sec_until_midnight = 24*3600 - (now.hour*3600 + now.minute*60
                                                        + now.second)
                        time.sleep(sec_until_midnight+5)
                        now = datetime.datetime.now()
                        if now.hour != 0:
                            print "ERROR: expected current time to be midnight but it is", now
                    now_seconds = 3600*now.hour + 60*now.minute + now.second # seconds since midnight of new day
                    event_time_seconds = 3600*(event_time[0]-24) + 60*event_time[1] + event_time[2]
    
                t_delay = event_time_seconds - now_seconds
                # Wait until the event is supposed to occur
                if t_delay > 0:
                    print "Delay %d" % t_delay
                    time.sleep(t_delay)
                    
                # Expect event to be action by bot
                if event_type == 'a':
                    id_str_mine = self.act(event_bot, attribute=0, verbose=1)
                    if id_str_mine != "":
                        num_post += 1
                        if phase == 'night':
                            t_observe = (7,30,num_post) # 7:30am next morning
                        elif phase == 'day':
                            t_observe = (19,30,num_post) # 7:30pm this evening
                        # Insert the observation event into the queue
                        # self.event_queue.put( (t_observe, event_bot, 'o') ) # commented
                        self.record_queue.put( (t_observe, event_bot, 'o') ) # new
                    else:
                        print "ERROR: act() failed!"
                elif event_type == 'o': # If event is an observation of response
                    # self.record(event_bot) # commented
                    print "ERROR: observation event should not occur here!"
                else:
                    print "ERROR: unknown event type!"

            current_time = datetime.datetime.now()
            if phase == 'night':
                # Calculate seconds until 7:30am of next day
                if current_time.hour >= 20:
                    # Means all posting finished before passing midnight
                    sec_until_nextphase = 24*3600 - (current_time.hour*3600 + current_time.minute*60
                                                     + current_time.second) # seconds until midnight
                    sec_until_nextphase += 7.5*3600 # add seconds until 7:30am                    
                else:
                    sec_until_nextphase = 7.5*3600 - (current_time.hour*3600 + current_time.minute*60
                                                    + current_time.second) # seconds until 7:30am                   
            elif phase == 'day':
                # Calculate seconds until 7:30pm of current day
                sec_until_nextphase = 19.5*3600 - (current_time.hour*3600 + current_time.minute*60
                                                   + current_time.second) # seconds until 7:30pm
            else:
                print "ERROR: unknown phase!"
                sec_until_nextphase = 0

            if sec_until_nextphase > 0:
                print "Seconds until nextphase %d" % sec_until_nextphase
                time.sleep(sec_until_nextphase)

            # While there are remaining recording events for this stage
            while self.record_queue.qsize():
    
                event = self.record_queue.get()
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
                    print "ERROR: action event should not occur here!"
                elif event_type == 'o': # If event is an observation of response
                    self.record(event_bot)
                else:
                    print "ERROR: unknown event type"

            # new
            print "Finished acting and recording response at", datetime.datetime.now()
            # Sort response and write to file
            self.list_response_tuples.sort()
            f = open("activities/activity_stage%d_comp%d.txt" % (num_stage,comp), "w")
            for t in self.list_response_tuples:
                f.write("%d %d %d\n" % (t[0], t[1], t[2])) # time follower_num bot_num
            f.close()
            f = open(self.logfilename, "a")
            f.write("Number of retweets by outsiders: %d\n" % self.num_response_outsiders)
            f.close()
            # Clear the list for the next day
            self.list_response_tuples = []
            self.num_response_outsiders = 0
            print "Finished writing activity file at", datetime.datetime.now()
                    
            # Sleep until beginning of next stage
            current_time = datetime.datetime.now()
            if phase == 'night':
                sec_until_nextphase = 8*3600 - (current_time.hour*3600 + current_time.minute*60
                                                + current_time.second) # seconds until 8am
            elif phase == 'day':
                sec_until_nextphase = 20*3600 - (current_time.hour*3600 + current_time.minute*60
                                                + current_time.second) # seconds until 8pm       
            else:
                print "ERROR: unknown phase!"
                sec_until_nextphase = 0

            if sec_until_nextphase > 0:
                print "Sleep for %d seconds until next stage" % sec_until_nextphase
                time.sleep(sec_until_nextphase)
            
            # Record connectivity matrix
            # self.record_network(list_to_track, num_stage)
            # self.record_network(map_follower_list_friends, num_stage) # commented
                        
            # Record follower details
            # self.observe_follower_detail(list_to_track, map_follower_lasttweet) # commented

            # Record follower's friends details
            # self.observe_follower_friend_detail(list_to_track, map_follower_map_friend_lasttweet)

            # Clear the list of tweets made by each bot during previous day
            self.map_bot_already_tweeted = { bot_id:[] for bot_id in range(0,4+1) }

            # Flip phase
            if phase == 'night':
                phase = 'day'
            elif phase == 'day':
                phase = 'night'
            else:
                print "ERROR: unknown phase!"


if __name__ == "__main__":
    
    exp = experiment(init_bots=1, init_observer=1)
