import os
import re
import fnmatch
import subprocess

class analyze:

    def __init__(self, dir_name):
        self.set_active = set() # set of people who took at least one measurable action
        self.map_user_count = {}
        self.total_response = 0
        self.dir_name = "/home/t3500/devdata/rlbot_data_highfrequency"
        # self.dir_name = dir_name

    def num_active(self):
        """
        Return number of followers who were active during the collection period
        Active = made at least one tweet or retweet or like
        """
    
        # For each records_*.csv, excluding records_{0,1,2,3,4}.csv
        # If number of lines in file is greater than 1, that means the 
        # person made at least one post. (First line is a header)
        # Add this user_id to the set
        regex = re.compile('records_.\.csv') # matches the bot records
        for filename in os.listdir(self.dir_name):
            if not re.match(regex, filename):
                if fnmatch.fnmatch(filename, 'records_*.csv'):
                    path_to_file = self.dir_name + "/" + filename
                    ret = subprocess.check_output(['wc', '-l', path_to_file])
                    num = int(ret.split(' ')[0]) # number of posts by person
                    if num > 1:
                        follower_id = filename.split('_')[1].split('.')[0]
                        if follower_id in self.map_user_count:
                            self.map_user_count[follower_id] += (num-1)
                        else:
                            self.map_user_count[follower_id] = (num-1)
                        self.set_active.add(follower_id)
    
        # For each retweeters_{0,1,2,3,4}.csv, each line is
        # tweet_id, retweeter_1_id, time_1, retweeter_2_id, time_2,...
        # Add these retweeter ids to the set
        regex = re.compile('retweeters_.\.csv') # matches bot retweeter files
        for filename in os.listdir(self.dir_name):
            if re.match(regex, filename):
                path_to_file = self.dir_name + "/" + filename
                f = open(path_to_file, 'r')
                for line in f:
                    # Discard tweet_id (first element) and newline (last element)
                    list_retweeter_time = line.split(',')[1:-1]
                    if len(list_retweeter_time) != 0:
                        idx = 0
                        while idx < len(list_retweeter_time):
                            self.total_response += 1
                            # Extract all odd elements
                            retweeter_id = list_retweeter_time[idx]
                            self.set_active.add(retweeter_id)
                            if retweeter_id in self.map_user_count:
                                self.map_user_count[retweeter_id] += 1
                            else:
                                self.map_user_count[retweeter_id] = 1
                            idx += 2
                f.close()
        
        # For each likers_{0,1,2,3,4}.csv, each line is
        # tweet_id, liker_1_id, liker_2_id,...
        # Add these liker ids to the set
        regex = re.compile('likers_.\.csv') # matches bot likers files
        for filename in os.listdir(self.dir_name):
            if re.match(regex, filename):
                path_to_file = self.dir_name + "/" + filename
                f = open(path_to_file, 'r')
                for line in f:
                    # Discard tweet_id (first element) and newline (last)
                    list_likers = line.split(',')[1:-1]
                    for liker_id in list_likers:
                        self.total_response += 1
                        self.set_active.add(liker_id)
                        if liker_id in self.map_user_count:
                            self.map_user_count[liker_id] += 1
                        else:
                            self.map_user_count[liker_id] = 1
                f.close()
                            
    def print_user_count(self):
        for key, value in self.map_user_count.iteritems():
            print key, value

    def get_total(self):
        return self.total_response

    def get_num_active(self):
        return len(self.set_active)