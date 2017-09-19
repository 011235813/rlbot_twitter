import rlbot

import time
import random
import datetime
import operator

class mfg:

    def __init__(self, init_bots=1, path='/home/t3500/devdata/mfg_round2'):
        # Path for storing data
        self.path = path
        
        # Initialize bots
        self.bots = []
        if init_bots:
            for idx in range(1, 9):
                self.bots.append( rlbot.rlbot(name='ml%d_gt'%idx,
                                              keyfile='key_bot%d.txt'%idx) )
        self.set_total_population = set()
        self.woeid_atlanta = 2357024
        # Map from user id_str to count of response to trending topic
        self.map_user_count = {}
        # Map from trend name to count of response by population to that
        # trend
        self.map_trend_count = {}
        # Map from user to most recent tweet measured
        self.map_user_lasttweet = {}
        # List of trend names measured at start of day
        self.list_trend_names = []
        

    def get_total_population(self, sourcefile='atlanta_popular.txt', outfile='followers_all.txt'):
        """
        For each account in sourcefile,
        use api.followers_ids with cursor to get 5000 follower IDs at a time,
        rate limit is 15 requests per 15 min
        Add these IDs to a set and save to file
        """
        
        # Counter for get_followers_cursored() rate limit
        counter_bot = 0
        # Bot to use for get_followers_cursored(). Cyclic
        choice_bot = 0

        # Read in accounts in Atlanta with high follower count
        f = open(sourcefile, 'r')
        list_source = f.readlines()
        f.close()
        list_source = map( (lambda x: x.strip()), list_source )
        
        source_num = 0
        for source in list_source:
            source_num += 1
            print "Source %d = %s" % (source_num, source)
            set_source = set()
            cursor = -1
            # while this source still has unseen followers
            while cursor != 0:
                list_followers, cursor = self.bots[choice_bot].get_followers_cursored(source, cursor=cursor)
                set_source.update(list_followers)

                counter_bot += 1
                if counter_bot == 15:
                    # go to next bot and reset counter
                    choice_bot = (choice_bot + 1) % len(self.bots)
                    print "Switch to %d" % choice_bot
                    counter_bot = 0

            # Add to total population
            self.set_total_population.update(set_source)
            # Write separate file for this particular source
            filename = self.path + '/' + ('followers_source%d.txt' % source_num)
            f = open(filename, 'w')
            for follower_id in set_source:
                f.write('%d\n' % follower_id)
            f.close()
        # Write to total population file
        f = open(self.path + '/' + outfile, 'w')
        for follower_id in self.set_total_population:
            f.write('%d\n' % follower_id)
        f.close()

    
    def filter_both(self, pred, iterable):
        list_pass = []
        list_fail = []
        for thing in iterable:
            if pred(thing):
                list_pass.append(thing)
            else:
                list_fail.append(thing)
        return list_pass, list_fail


    def filt(self, user):
        """ 
        Argument:
        1. user - user object

        Checks whether user is based in Atlanta and account is not
        protected (i.e. tweets can be seen)
        """
        locations = ['Atlanta, GA', 'Atlanta']
        if (user.location in locations) and not user.protected:
            return True
        else:
            return False


    def filter_location(self, sourcefile='followers_all.txt', outfile1='population_location_in.txt', outfile2='population_location_out.txt'):
        """
        Arguments:
        1. sourcefile - each line is a user ID
        2. location - list of filter criteria
        3. outfile1 - output file of user ID that satisfy location criteria
        4. outfile2 - output file of user ID that fail location criteria

        Creates outfile1 and outfile2
        Expected to take 3.337e6 / (8 * 900 * 100) / 4 = 1.15 hours
        using 8 bots that each makes 900 requests per 15min,
        with each request handling 100 user IDs
        """

        # Read sourcefile
        f = open(self.path + '/' + sourcefile, 'r')
        list_ids = f.readlines()
        f.close()
        list_ids = map( (lambda x: x.strip()), list_ids )

        # Counter for get_followers_cursored() rate limit
        counter_bot = 0
        # Bot to use for get_followers_cursored(). Cyclic
        choice_bot = 0        

        num_total = len(list_ids)
        idx = 0
        while idx < num_total:
            
            print "idx = %d" % idx
            # Process 100 user IDs with each request
            list_users = self.bots[choice_bot].get_users(list_ids[idx:min(idx+100,num_total)])
            # print len(list_users)
            counter_bot += 1
            if counter_bot == 900:
                # go to next bot and reset counter
                choice_bot = (choice_bot + 1) % len(self.bots)
                print "Switch to %d" % choice_bot
                counter_bot = 0
            
            # Filter for location
            list_pass, list_fail = self.filter_both(self.filt, list_users)
            # print "list_pass", len(list_pass), "list_fail", len(list_fail)

            # Write those that satisfy location criteria
            f = open(self.path + '/' + outfile1, 'a')
            for user in list_pass:
                f.write('%d\n' % user.id)
            f.close()

            # Write those that fail location criteria
            f = open(self.path + '/' + outfile2, 'a')
            for user in list_fail:
                f.write('%d\n' % user.id)
            f.close()
            
            idx += 100
        
        
    def wait_until(self, nextday, hour, minute=0, second=0):
        """
        Sleep until input hour
        """
        t_now = datetime.datetime.now()

        # Check whether desired start time is the next day
        if nextday:
            # Wait until midnight
            sec_until_midnight = 24*3600 - (t_now.hour*3600 + t_now.minute*60 + t_now.second)
            print "Sleep for %d seconds until midnight" % sec_until_midnight
            time.sleep(sec_until_midnight + 10)

        t_now = datetime.datetime.now()
        sec_until_start = hour*3600 + minute*60 + second - (t_now.hour*3600 + t_now.minute*60 + t_now.second)
        if sec_until_start > 0:
            print "Sleep for %d seconds until (%d,%d,%d)" % (sec_until_start, hour, minute, second)
            time.sleep(sec_until_start)
        

    def initialize_map(self, list_uid):
        """
        Argument:
        1. list_uid - list of user IDs
        Return
        1. map from user ID to ID of most recent tweet

        Called at start of day.
        For 75362 people using 8 bots with limit 900 per 15min,
        requires 75362 / (8 * 900) / 4 = 2.6 hours
        """
        print "Inside initialize_map() at ", datetime.datetime.now()
        # Map from user id to id of last post
        map_user_lasttweet = {}
        # Counter for get_timeline() rate limit
        counter_bot = 0
        # Bot to use for get_timeline(). Cyclic
        choice_bot = 0        

        for uid in list_uid:
            tweet_list = self.bots[choice_bot].get_timeline(uid, n=1)
            # Store most recent post by follower_id_str, if post exists
            if len(tweet_list) != 0:
                map_user_lasttweet[uid] = tweet_list[0].id_str
            else:
                map_user_lasttweet[uid] = ''            

            # Check whether need to switch to another bot for get_timeline
            # Limit is 900req/15min, leave margin of 10
            counter_bot += 1
            if counter_bot == 895:
                # go to next bot
                choice_bot = (choice_bot + 1) % len(self.bots) 
                print "Switch to %d at" % choice_bot, datetime.datetime.now()
                counter_bot = 0 # reset counter

        print "Exiting initialize_maps() at ", datetime.datetime.now()

        return map_user_lasttweet


    def process_day(self, list_ids, map_user_lasttweet, list_trend_names):
        """
        Arguments:
        1. list_ids - list of id_str of users in population
        2. map_user_lasttweet - map from user id_str to id_str of last tweet before start of day
        3. list_trend_names - list of names of trends determined at start of day
        
        Called at end of day to update population response counts
        """
        print "Inside process_day() at ", datetime.datetime.now()
        # Counter for get_timeline_since() rate limit
        counter_bot = 0
        # Bot to use for get_timeline_since(). Cyclic
        choice_bot = 0
        # Initialize rate limit with margin
        request_limit = (900 - 5)

        for uid in list_ids:
            last_tweet = map_user_lasttweet[uid]
            if last_tweet != '':
                tweets = self.bots[choice_bot].get_timeline_since(uid, since=last_tweet)
            else:
                tweets = self.bots[choice_bot].get_timeline(uid, verbose=0)

            # Check whether need to switch to another bot for get_timeline
            counter_bot += 1
            if counter_bot >= request_limit:
                # go to next bot
                choice_bot = (choice_bot + 1) % len(self.bots) 
                limits = self.bots[choice_bot].api.rate_limit_status()
                request_limit = self.bots[choice_bot].get_limits(limits, 'timeline')
                print "Switch to ml%d_gt with limit %d -5 at " % (choice_bot+1, request_limit), datetime.datetime.now()
                request_limit = max(0, request_limit-5) # apply margin
                counter_bot = 0 # reset counter

            # Determine whether any of user's tweets during day is a response to any trend
            # Increment count by one if so
            responded = 0
            for tweet in tweets:
                for trend in list_trend_names:
                    if trend in tweet.text:
                        # Increment user count
                        self.map_user_count[uid] += 1
                        responded = 1
                        break
                if responded:
                    # Stop searching through tweets if found one response
                    break

        print "Exiting process_day() at ", datetime.datetime.now()


    def get_trends(self):
        """
        Returns:
        1. list_trend_names
        2. list_pairs - list of pairs of form (tweet_volume, trend name)
        """

        # Use any bot to do this
        list_trends = self.bots[0].get_trends_place(2357024, 'Atlanta')

        list_trend_names = []
        list_pairs = []
        # Create list of pairs (count, name)
        for trend in list_trends:
            count = trend['tweet_volume']
            if count == None:
                count = 0
            list_pairs.append( (count, trend['name']) )
        # Sort the pairs in descending order, first by tweet_volume then
        # by text
        list_pairs.sort(key=operator.itemgetter(0,1), reverse=True)
        for pair in list_pairs:
            list_trend_names.append( pair[1] )

        return list_trend_names, list_pairs


    def write_activity(self, day):
        """
        Write file with format
        <uid>,<number of days when user has responded to trending topic, up to current day>
        Overwrites previous day file
        """
        print "Inside write_activity() at ", datetime.datetime.now()
        f = open(self.path + '/' + 'map_user_count_day%d.csv' % day, 'w')
        for uid, count in self.map_user_count.iteritems():
            f.write('%s,%d\n' % (uid, count))
        f.close()


    def record_population_activity(self, day_start=0, nextday=1, hour_start=1, num_days=7, population='population_location_in_part1.txt'):
        """
        Arguments:
        1. day_start - in case need to restart function
        2. nextday - whether or not start on the next day
        3. hour_start - 0-24
        4. num_days - number of days to record activity
        5. population - name of file of user IDs of people to track

        Output:
        A map from userid to count of response to daily trending topics
        within the span of num_days.

        """

        # Read in population
        f = open(self.path + '/' + population, 'r')
        list_ids = f.readlines()
        f.close()
        list_ids = map( (lambda x: x.strip()), list_ids )        

        # Initialize map from user id_str to count of response to trends
        for uid in list_ids:
            self.map_user_count[uid] = 0

        day = day_start
        self.wait_until(nextday=nextday, hour=hour_start)

        while day < num_days:
            day += 1
            print "Day %d" % day

            # Wait until 6am
            self.wait_until(nextday=0, hour=6)
                
            # Get map from user ID to ID of last tweet
            map_user_lasttweet = self.initialize_map(list_ids)
                
            # Wait until 9am
            self.wait_until(nextday=0, hour=9)

            # Get trends at start of day
            list_trend_names, list_pairs = self.get_trends()

            # Record trends at start of day
            f = open(self.path + '/' + 'trends_day%d_start.csv' % day, 'w')
            for pair in list_pairs:
                s = '%d,%s\n' % (pair[0], pair[1])
                f.write(s.encode('utf8'))
            f.close()

            # Wait until 12 midnight
            self.wait_until(nextday=0, hour=24)

            # Get trends at end of day (not really used for filtering)
            list_trend_names_end, list_pairs_end = self.get_trends()

            # Record list of trends at end of day 
            f = open(self.path + '/' + 'trends_day%d_end.csv' % day, 'w')
            for pair in list_pairs_end:
                s = '%d,%s\n' % (pair[0], pair[1])
                f.write(s.encode('utf8'))
            f.close()           
            
            # At end of day, for each user, get list of posts by that user 
            # scan through each post
            # find out whether the person responded to a trend during day. 
            self.process_day(list_ids, map_user_lasttweet, list_trend_names)

            self.write_activity(day)


    def filter_active(self, num_days=4, criteria=1, 
                      outfile='population_active.txt'):
        """
        Filters the files map_user_count_day*.csv to find
        the subset of people who respond to trends

        Argument:
        0. num_days - number of days for which there are 
        'map_user_count_day*.csv' files
        1. criteria - number of responses that users must have made to be
        considered "active"
        2. outfile - filename of output file containing the list of 
        filtered user_ids
        """
        
        map_user_count = {}

        f = open(self.path+'/'+'map_user_count_day0.csv', 'r')
        lines = f.readlines()
        f.close()
        lines = map( (lambda x: x.strip().split(',')), lines)
        
        # Populate key-value pairs using day0
        for pair in lines:
            map_user_count[pair[0]] = int(pair[1])

        # For the rest of the days
        for day in range(1, num_days):
            f = open(self.path+'/'+'map_user_count_day%d.csv' % day, 'r')
            lines = f.readlines()
            f.close()
            lines = map( (lambda x: x.strip().split(',')), lines)
            for pair in lines:
                map_user_count[pair[0]] += int(pair[1])

        # Filter using criteria and write to output file
        f = open(self.path+'/'+outfile, 'w')
        for key, val in map_user_count.iteritems():
            if val >= criteria:
                f.write('%s\n' % key)
        f.close()


    def process_hour(self, list_ids):
        """
        Arguments:
        1. list_ids - list of id_str of users in population
        
        Called at start of every hour to record distribution over trends
        Also updates self.map_user_lasttweet to prepare for the next hour
        """
        print "Inside process_hour() at ", datetime.datetime.now()
        # Counter for get_timeline_since() rate limit
        counter_bot = 0
        # Bot to use for get_timeline_since(). Cyclic
        choice_bot = 0
        # Initialize rate limit with margin
        request_limit = (900 - 5)

        for uid in list_ids:
            last_tweet = self.map_user_lasttweet[uid]
            if last_tweet != '':
                tweets = self.bots[choice_bot].get_timeline_since(uid, since=last_tweet)
            else:
                tweets = self.bots[choice_bot].get_timeline(uid, verbose=0)

            # Check whether need to switch to another bot for get_timeline
            counter_bot += 1
            if counter_bot >= request_limit:
                # go to next bot
                choice_bot = (choice_bot + 1) % len(self.bots) 
                limits = self.bots[choice_bot].api.rate_limit_status()
                request_limit = self.bots[choice_bot].get_limits(limits, 'timeline')
                print "Switch to ml%d_gt with limit %d -5 at " % (choice_bot+1, request_limit), datetime.datetime.now()
                request_limit = max(0, request_limit-5) # apply margin
                counter_bot = 0 # reset counter

            # Determine whether any of user's tweets since the last tweet
            # is a response to any trend
            # Increment count by one if so
            responded = 0
            for trend in self.list_trend_names:
                for tweet in tweets:
                    if trend in tweet.text:
                        # Increment trend count
                        self.map_trend_count[trend] += 1
                        responded = 1
                        # Stop going through tweets for this trend,
                        # since each person only counts once
                        break
            # If did not respond, then user belongs to the no_response
            # category
            if responded == 0:
                self.map_trend_count['no_response'] += 1
                
            # Update self.map_user_lasttweet
            if len(tweets) != 0:
                self.map_user_lasttweet[uid] = tweets[0].id_str
            else:
                self.map_user_lasttweet[uid] = last_tweet

        print "Exiting process_hour() at ", datetime.datetime.now()


    def record_distribution(self, day_start=0, nextday=1, hour_start=1, num_days=30, population='population_active.txt'):
        """
        Primary function for recording the hourly 
        evolution of the distribution
        of people in population_active.txt, with respect to daily trends

        Arguments:
        1. day_start - in case need to restart function
        2. nextday - whether or not start on the next day
        3. hour_start - 0 to 24
        4. num_days - number of days to record
        5. population - name of file of user IDs of people to track

        Output:
        Daily output file with format:
        topic_1, topic_2, ... , topic_d
        num_hour1, num_hour1, ..., num_hour1
        num_hour2, num_hour2, ..., num_hour2
        ...
        num_hourN, num_hourN, ..., num_hourN
        """
        
        # Read in population
        f = open(self.path + '/' + population, 'r')
        list_ids = f.readlines()
        f.close()
        list_ids = map( (lambda x: x.strip()), list_ids )        

        day = day_start
        self.wait_until(nextday=nextday, hour=hour_start)

        while day < num_days:
            
            day += 1
            print "Day %d" % day

            # Wait until 8am
            self.wait_until(nextday=0, hour=8)
                
            # Get map from user ID to ID of last tweet
            self.map_user_lasttweet = self.initialize_map(list_ids)
                
            # Wait until 9am
            self.wait_until(nextday=0, hour=9)

            # Get trends at start of day
            self.list_trend_names, list_pairs = self.get_trends()

            # Record trends at start of day
            f = open(self.path+'/distribution/'+'trends_day%d.csv' % day, 'w')
            for pair in list_pairs:
                s = '%d,%s\n' % (pair[0], pair[1])
                f.write(s.encode('utf8'))
            f.close()

            # Initialize distribution file
            list_temp = ['no_response'] + self.list_trend_names
            list_temp.append('\n')
            f = open(self.path+'/distribution/'+'trend_distribution_day%d.csv' % day, 'a')            
            f.write( (','.join(list_temp)).encode('utf8') )
            f.close()

            # Initialize map from trend to count
            for name in self.list_trend_names:
                self.map_trend_count[name] = 0
            # Add additional category for people who did not
            # respond to trends within the hour
            self.map_trend_count['no_response'] = 0

            hour = 9
            # For each hour during the rest of day
            while hour <= 24:
                self.wait_until(nextday=0, hour=hour)

                # Record distribution over topics
                # Also updates self.map_user_lasttweet
                self.process_hour(list_ids)
                
                # Record distribution
                list_temp = [ self.map_trend_count['no_response'] ]
                for name in self.list_trend_names:
                    list_temp.append( self.map_trend_count[name] )
                list_temp = map(str, list_temp)
                list_temp.append('\n')
                f = open(self.path+'/distribution/'+'trend_distribution_day%d.csv' % day, 'a')            
                f.write( ','.join(list_temp) )
                f.close()                

                # Clear map_trend_count for the next hour
                for name in self.map_trend_count.iterkeys():
                    self.map_trend_count[name] = 0
                
                hour += 1


            
