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
        
        
