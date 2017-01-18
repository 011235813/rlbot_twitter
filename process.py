import os
import re
import fnmatch
import subprocess
import random
import datetime

class process:

    def __init__(self, choice=0):
        
        if choice == 0:
            self.dir_name = "/home/t3500/devdata/rlbot_data_highfrequency"
        elif choice == 1:
            self.dir_name = "/home/t3500/devdata/rlbot_data_secondorder"        

        self.map_userid_number = {}

    def create_id(self, matrix_file, f_write):
        """
        Input:
        matrix_file - adjacency matrix representation of the graph

        Extracts list of followers, randomize the list, number them from 1 to N
        Creates writes mapping file that maps each user_id to its number
        Also writes network.txt of format
        u_i v_i
        where u_i follows v_i
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
        f = open(f_write, 'w')
        for idx in range(1, N+1):
            f.write("%s,%d\n" % (list_userids[idx-1], idx))
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

