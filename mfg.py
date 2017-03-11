import rlbot

import time
import random
import datetime

class mfg:

    def __init__(self, init_bots=1):
        self.path = '/home/t3500/devdata/mfg'
        
        self.bots = []
        if init_bots:
            for idx in range(6, 9):
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


                
