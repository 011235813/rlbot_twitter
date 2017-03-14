import rlbot

import time
import random
import datetime

class mfg:

    def __init__(self, init_bots=1):
        self.path = '/home/t3500/devdata/mfg'
        
        self.bots = []
        if init_bots:
            for idx in range(1, 9):
                self.bots.append( rlbot.rlbot(name='ml%d_gt'%idx,
                                              keyfile='key_bot%d.txt'%idx) )
        self.set_total_population = set()
        self.woeid_atlanta = 2357024
        # Map from user id_str to count of response to trending topic
        self.map_user_count = {}
        

    def get_total_population(self, sourcefile='atlanta_popular.txt', outfile='followers_all.txt'):
        """
        For each account in atlanta_popular
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
            print "Sleep for %d seconds until start of day" % sec_until_start
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
            if counter_bot == 890:
                # go to next bot
                choice_bot = (choice_bot + 1) % len(self.bots) 
                print "Switch to %d" % choice_bot
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

        for uid in list_ids:
            last_tweet = map_user_lasttweet[uid]
            if last_tweet != '':
                tweets = self.bots[choice_bot].get_timeline_since(uid, since=last_tweet)
            else:
                tweets = self.bots[choice_bot].get_timeline(uid, verbose=0)


            # Check whether need to switch to another bot for get_timeline
            counter_bot += 1
            if counter_bot == 890:
                # go to next bot
                choice_bot = (choice_bot + 1) % len(self.bots) 
                print "Switch to %d" % choice_bot
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
        # Extract list of trend names
        # Also create list of pairs (count, name)
        for trend in list_trends:
            list_trend_names.append(trend['name'])
            count = trend['tweet_volume']
            if count == None:
                count = 0
            list_pairs.append( (count, trend['name']) )
        # Sort the pairs in descending order
        list_pairs.sort(reverse=True)

        return list_trend_names, list_pairs


    def write_activity(self):
        """
        Write file with format
        <uid>,<number of days when user has responded to trending topic, up to current day>
        Overwrites previous day file
        """
        print "Inside write_activity() at ", datetime.datetime.now()
        f = open(self.path + '/' + 'map_user_count.csv', 'w')
        for uid, count in self.map_user_count.iteritems():
            f.write('%s,%d\n' % (uid, count))
        f.close()


    def record_population_activity(self, num_days=7, population='population_location_in_part1.txt'):
        """
        Arguments:
        1. num_days - number of days to record activity
        2. population - name of file of user IDs of people to track

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

        day = 0
        self.wait_until(nextday=1, hour=1)

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
                f.write('%d,%s\n' % (pair[0], pair[1]))
            f.close()

            # Wait until 12 midnight
            self.wait_until(nextday=0, hour=24)

            # Get trends at end of day (not really used for filtering)
            list_trend_names_end, list_pairs_end = self.get_trends()

            # Record list of trends at end of day 
            f = open(self.path + '/' + 'trends_day%d_end.csv' % day, 'w')
            for pair in list_pairs_end:
                f.write('%d,%s\n' % (pair[0], pair[1]))
            f.close()           
            
            # At end of day, for each user, get list of posts by that user 
            # scan through each post
            # find out whether the person responded to a trend during day. 
            self.process_day(list_ids, map_user_lasttweet, list_trend_names)

            self.write_activity()

