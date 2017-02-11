import os
import re
import fnmatch
import subprocess
import random
import datetime
import rlbot

class process:

    def __init__(self, choice=0):
        
        if choice == 0:
            self.dir_name = "/home/t3500/devdata/rlbot_data_highfrequency"
        elif choice == 1:
            self.dir_name = "/home/t3500/devdata/rlbot_data_secondorder"        
        self.bot = rlbot.rlbot('username124816','keys.txt')
        # Map from twitter id (string) to anonymized number (int)
        self.map_userid_number = {}

    def create_id(self, matrix_file='matrix_day72_backup.csv', f_write='map_userid_id.csv'):
        """
        Input:
        matrix_file - adjacency matrix representation of the graph

        Extracts list of followers, randomize the list, number them from 6 to N+5
        Appends to mapping file that maps each user_id to its number
        Assumes that mapping file already contains mapping from bots to 1...5
        """
        path_to_file = self.dir_name + "/" + matrix_file
        f = open(path_to_file, 'r')
        first_line = f.readline().strip()
        f.close()

        list_userids = first_line.split(',')[1:-1] # remove first and last
        set_userids = set(list_userids)
        if len(set_userids) != len(list_userids):
            print "Duplicates exist!"
            return
        N = len(list_userids)
        # Randomize
        for idx in range(0,N-1):
            temp = list_userids[idx]
            idx_rand = random.randint(idx+1,N-1)
            # Swap
            list_userids[idx] = list_userids[idx_rand]
            list_userids[idx_rand] = temp
        
        # Create mapping and store to file
        f = open(f_write, 'a')
        for idx in range(N):
            f.write("%s,%d\n" % (list_userids[idx], idx+6))
        f.close()

    def create_network(self, f_map='map_userid_id.csv', f_matrix='matrix_day72_backup.csv', f_output='network.txt'):
        """
        Arguments:
        f_map - file with rows "userid,id", where id ranges from 1 to N.
        f_matrix - e.g. matrix_day72_backup.csv
        f_output - file with rows "u_i v_i" if u_i follows v_i
        """
        # Read map file
        f = open(f_map, 'r')
        lines = f.readlines()
        f.close()
        for line in lines:
            pair = line.strip().split(',')
            userid = pair[0]
            num = int(pair[1])
            self.map_userid_number[userid] = num
            
        # Read matrix file
        path_to_file = self.dir_name + "/" + f_matrix
        f = open(path_to_file, 'r')
        list_followers = f.readline().strip().split(',')[1:-1]
        N = len(list_followers)
        # Open file for writing
        f_write = open(f_output, 'w')
        for line in f:
            list_binary = line.strip().split(',')
            follower_userid = list_binary[0] # userid of follower
            follower_number = self.map_userid_number[follower_userid]
            for idx in range(1,N+1):
                if list_binary[idx] == '1':
                    friend_userid = list_followers[idx-1]
                    friend_number = self.map_userid_number[friend_userid]
                    f_write.write("%d %d\n" % (follower_number, friend_number))
        f_write.close()
        f.close()

    
    def append_network_bots(self, f_output='network.txt'):
        """
        For each bot, for all followers of the bot that exists in matrix_day72.csv,
        append the relationship "follower_id_anonymized unique_bot_id" to f_output

        This is only to add the bots into network.txt
        Relationships among the followers were already added by create_network()
        
        Requires read_map_file() to be run before running this function
        """
        # Open file for appending
        f = open(f_output,'a')
        for bot_id in range(1, 5+1):
            list_followers = self.bot.get_followers('ml%d_gt' % bot_id)
            for follower_id in list_followers:
                if follower_id in self.map_userid_number:
                    f.write("%d %d\n" % (self.map_userid_number[follower_id],
                                         bot_id))
        f.close()


    def read_map_file(self, f_map='map_userid_id.csv'):
        # Read map file
        f = open(f_map, 'r')
        lines = f.readlines()
        f.close()
        for line in lines:
            pair = line.strip().split(',')
            userid = pair[0]
            num = int(pair[1])
            self.map_userid_number[userid] = num        


    def create_activity(self, f_output='activity.txt'):
        """
        f_output - file with rows "t_i u_i [outside?]" for retweet at time t_i by 
        user u_i, and outside is either 1 (if u_i is outside follower network)
        or 0 if inside

        Need to call read_map_file() prior to calling this function
        """
        list_tuple = []
        epoch = datetime.datetime.utcfromtimestamp(0)
        count_outside = 0
        for bot_id in range(0,5):
            print bot_id
            filename = "retweeters_%d_backup.csv" % bot_id
            path_to_file = self.dir_name + "/" + filename
            f = open(path_to_file, 'r')
            for line in f:
                # Discard tweet_id (first element) and newline (last element)
                list_retweeter_time = line.split(',')[1:-1]
                if len(list_retweeter_time) != 0:
                    idx = 0
                    while idx < len(list_retweeter_time):
                        retweeter_id = list_retweeter_time[idx]
                        if retweeter_id in self.map_userid_number:
                            retweeter_num = self.map_userid_number[retweeter_id]
                            outside = 0
                        else:
                            retweeter_num = -1
                            outside = 1
                            count_outside += 1
                        idx += 1
                        # year-month-day-hour-min-second (UTC - 4)
                        tweet_time = list_retweeter_time[idx]
                        dt_local = datetime.datetime.strptime(tweet_time, '%Y-%m-%d-%H-%M-%S')
                        dt_utc = dt_local + datetime.timedelta(hours=4)
                        seconds = (dt_utc - epoch).total_seconds()
                        list_tuple.append( (seconds,retweeter_num,outside) )
                        idx += 1
        list_tuple.sort()
        f_write = open(f_output, 'w')
        for t in list_tuple:
            f_write.write("%d %d %d\n" % (t[0], t[1], t[2]))
        f_write.close()
        print "Total number of retweets from outside network = %d" % count_outside


    def create_activity_all(self, f_output='activity_all.txt'):
        """
        f_output - file with rows "t_i u_i" for retweet at time t_i by 
        user u_i

        Need to call read_map_file() prior to calling this function
        """
        list_tuple = []
        epoch = datetime.datetime.utcfromtimestamp(0)        

        # For each records_*.csv, excluding records_{0,1,2,3,4}.csv
        regex = re.compile('records_.\.csv')
        for filename in os.listdir(self.dir_name):
            if not re.match(regex, filename):
                if fnmatch.fnmatch(filename, 'records_*.csv'):
                    path_to_file = self.dir_name + "/" + filename
                    ret = subprocess.check_output(['wc', '-l', path_to_file])
                    num = int(ret.split(' ')[0])
                    # If follower has activity
                    if num > 1:
                        follower_id = filename.split('_')[1].split('.')[0]
                        # Extract id of follower, get the anonymous number
                        if follower_id in self.map_userid_number:
                            follower_num = self.map_userid_number[follower_id]
                            # Parse through file
                            f = open(path_to_file,'r')
                            # Skip first line
                            f.readline()
                            for line in f:
                                line_split = line.split(',')
                                # Extract the time of post, create the pair
                                # year-month-day-hour-min-second (UTC - 4)
                                date_and_time = line_split[1]
                                dt_local = datetime.datetime.strptime(date_and_time, '%Y-%m-%d-%H:%M:%S')
                                dt_utc = dt_local + datetime.timedelta(hours=4)
                                seconds = (dt_utc - epoch).total_seconds()
                                list_tuple.append((seconds,follower_num))           
        # Now append the bot activity
        for bot_id in range(0,5):
            print bot_id
            filename = "records_%d.csv" % bot_id
            path_to_file = self.dir_name + "/" + filename
            f = open(path_to_file, 'r')
            # Skip first line
            f.readline()
            for line in f:
                line_split = line.split(',')
                # Extract time of post, create the pair
                date_and_time = line_split[1]
                dt_local = datetime.datetime.strptime(date_and_time, '%Y-%m-%d-%H-%M-%S')
                dt_utc = dt_local + datetime.timedelta(hours=4)
                seconds = (dt_utc - epoch).total_seconds()
                list_tuple.append((seconds, bot_id+1))

        # Sort all pairs based on time of post
        list_tuple.sort()
        # Write f_output
        f_write = open(f_output, 'w')
        for t in list_tuple:
            f_write.write("%d %d\n" % (t[0], t[1]))
        f_write.close()


    def create_activity_history(self, f_output='activity_history.txt'):
        """
        Creates file with following format:
        n
        <UTC time since epoch in seconds> <retweeter_num> <bot_num>
        <UTC time since epoch in seconds> <retweeter_num> <bot_num>
        ...
        <UTC time since epoch in seconds> <retweeter_num> <bot_num>
        n
        <UTC time since epoch in seconds> <retweeter_num> <bot_num>
        ...
        where n indicates number of subsequent lines defining a stage
        of 12 hours from 8am to 8pm and 8pm to 8am,
        time is time of post, 
        retweeter_num is label of the retweeter according to map_userid_id.csv,
        (which could be the bot as well)
        and bot_num is the (bot_id + 1) of the bot who made the original post 
        """

        epoch = datetime.datetime.utcfromtimestamp(0)
        list_tuples = []

        # Gather all the posts made by bots in records_*.csv
        print "Gathering bot posts"
        for bot_id in range(0,5):
            print bot_id
            filename = "records_%d.csv" % bot_id
            path_to_file = self.dir_name + "/" + filename
            f = open(path_to_file, 'r')
            # Skip first line
            f.readline()
            for line in f:
                line_split = line.split(',')
                # Extract time of post, create the pair
                date_and_time = line_split[1]
                dt_local = datetime.datetime.strptime(date_and_time, '%Y-%m-%d-%H-%M-%S')
                if (dt_local.year == 2016 and 
                    (dt_local.month < 11 or (dt_local.month == 11 and dt_local.day < 7))):
                    dt_utc = dt_local + datetime.timedelta(hours=4)
                else:
                    dt_utc = dt_local + datetime.timedelta(hours=5)
                seconds = (dt_utc - epoch).total_seconds()
                list_tuples.append((seconds, bot_id+1, bot_id+1))
        
        # Gather all the retweets by followers
        count_outside = 0
        count_inside = 0
        print "Gathering retweets"
        for bot_id in range(0,5):
            print bot_id
            filename = "retweeters_%d.csv" % bot_id
            path_to_file = self.dir_name + "/" + filename
            f = open(path_to_file, 'r')
            for line in f:
                # Discard tweet_id (first element) and newline (last element)
                list_retweeter_time = line.split(',')[1:-1]
                if len(list_retweeter_time) != 0:
                    idx = 0
                    while idx < len(list_retweeter_time):
                        retweeter_id = list_retweeter_time[idx]
                        if retweeter_id in self.map_userid_number:
                            retweeter_num = self.map_userid_number[retweeter_id]
                            count_inside += 1
                        else:
                            retweeter_num = -1
                            count_outside += 1
                        idx += 1
                        if retweeter_num != -1:
                            # year-month-day-hour-min-second (UTC - 4)
                            tweet_time = list_retweeter_time[idx]
                            dt_local = datetime.datetime.strptime(tweet_time, '%Y-%m-%d-%H-%M-%S')
                            dt_utc = dt_local + datetime.timedelta(hours=4)
                            seconds = (dt_utc - epoch).total_seconds()
                            list_tuples.append( (seconds, retweeter_num, bot_id+1) )
                        idx += 1
        print "Retweets from inside = %d" % count_inside
        print "Retweets from outside = %d" % count_outside
        
        # Sort the entire list by time
        list_tuples.sort()

        # Get the time of first event
        first_event_time = list_tuples[0][0] # seconds since epoch of utc time
        # Convert to EST (daylight savings)
        first_event_time = datetime.datetime.utcfromtimestamp(first_event_time) + datetime.timedelta(hours=-4)
        # Get start time of stage
        if first_event_time.hour < 20 and first_event_time.hour >= 8:
            # Day stage
            start = datetime.datetime(first_event_time.year, first_event_time.month,
                                      first_event_time.day, 8, 0, 0)
        elif first_event_time.hour >= 20 or first_event_time.hour < 8:
            # Night stage
            start = datetime.datetime(first_event_time.year, first_event_time.month,
                                      first_event_time.day-1, 20, 0, 0)
        print start
        # Convert back into seconds since epoch in utc time
        start_utc_seconds = (start + datetime.timedelta(hours=4) - epoch).total_seconds()
        
        # Partition into 12 hour sections
        print "Writing file"
        stage_end = start_utc_seconds + 12*60*60
        idx_prev = 0
        f = open(f_output, 'w')
        for idx in range(len(list_tuples)):
            if list_tuples[idx][0] < stage_end:
                if idx == len(list_tuples)-1:
                    # at last item
                    count = idx - idx_prev + 1
                    f.write('%d\n' % count)
                    for idx2 in range(idx_prev, idx+1):
                        triple = list_tuples[idx2]
                        f.write('%d %d %d\n' % (triple[0], triple[1], triple[2]))
                idx += 1
            else:
                count = idx - idx_prev
                f.write('%d\n' % count)
                for idx2 in range(idx_prev, idx):
                    triple = list_tuples[idx2]
                    f.write('%d %d %d\n' % (triple[0], triple[1], triple[2]))
                idx_prev = idx
                stage_end += 12*60*60
                idx += 1
        f.close()
