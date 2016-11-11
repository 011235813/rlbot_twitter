import os
import re
import fnmatch
import subprocess
import rlbot

class analyze:

    def __init__(self, choice=0):
        # Subset of followers who took at least one measurable action within the entire
        # duration
        self.set_active = set() 
        # Subset of followers who responded at least once to the bot's posts
        self.set_active_response = set()
        # Map from follower ID to count of the number of tweets they made
        self.map_user_count = {}
        # Map from follower ID to count of the number of responses to the bot
        self.map_user_response = {}
        # Sum of response (likes and retweets) to bots' posts, over all followers
        self.total_response = 0
        # Total number of tweets (not limited to retweet of bots' posts) made by all followers
        self.total_activity = 0
        # Map from follower ID to map from friend ID to list of (tweet ID, tweet time) pairs
        self.map_follower_map_friend_list = {}
        # Set of all friends of followers of bots
        self.set_friends = set()
        if choice == 0:
            self.dir_name = "/home/t3500/devdata/rlbot_data_highfrequency"
        elif choice == 1:
            self.dir_name = "/home/t3500/devdata/rlbot_data_secondorder"

    def calc_activity(self):
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
                            self.set_active_response.add(retweeter_id)
                            self.set_active.add(retweeter_id)
#                            if retweeter_id in self.map_user_count:
#                                self.map_user_count[retweeter_id] += 1
#                            else:
#                                self.map_user_count[retweeter_id] = 1
                            if retweeter_id in self.map_user_response:
                                self.map_user_response[retweeter_id] += 1
                            else:
                                self.map_user_response[retweeter_id] = 1
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
                        self.set_active_response.add(liker_id)
                        self.set_active.add(liker_id)
#                        if liker_id in self.map_user_count:
#                            self.map_user_count[liker_id] += 1
#                        else:
#                            self.map_user_count[liker_id] = 1
                        if liker_id in self.map_user_response:
                            self.map_user_response[liker_id] += 1
                        else:
                            self.map_user_response[liker_id] = 1
                f.close()

        for key, value in self.map_user_count.iteritems():
            self.total_activity += value

    def calc_friends(self):
        """
        For each follower, parse the file "friends_of_<follower-id>.csv"
        Create map from follower_id to map from friend_id to list of 
        (tweet_id, time) pairs
        """
        for filename in os.listdir(self.dir_name):
            if fnmatch.fnmatch(filename, 'friends_of_*.csv'):
                follower_id = filename.split('_')[2].split('.')[0]
                map_friend_list = {}
                path_to_file = self.dir_name + "/" + filename
                f = open(path_to_file, 'r')
                f.readline() # skip the first line
                for line in f:
                    line_split = line.split(',')
                    friend_id = line_split[0]
                    tweet_id = line_split[1]
                    tweet_time = line_split[2]
                    pair = (tweet_id, tweet_time)
                    self.set_friends.add(friend_id)
                    if friend_id in map_friend_list:
                        map_friend_list[friend_id].append( pair )
                    else:
                        map_friend_list[friend_id] = [ pair ]
                
                self.map_follower_map_friend_list[follower_id] = map_friend_list
                f.close()
                
    def consolidate(self, outfile):
        """
        Combine information from records_{0-4}.csv, retweeters_{0-4}.csv
        and likers_{0-4}.csv to produce a single tab-separated output data file
        """
        # Everything gets store here first, then will be sorted by time
        # and then written into the final file
        list_combined = []
        # Need to instantiate bot to retrieve tweets that the bots posted
        bot = rlbot.rlbot('username124816','keys.txt')

        for bot_id in range(0,5):
            print "Parsing for bot %d" % bot_id
            with open(self.dir_name + '/records_%d.csv' % bot_id) as f:
                records = [line.strip('\n').split(',') for line in f.readlines()]
            # Remove the header row
            del records[0]
            records.sort()
            with open(self.dir_name + '/retweeters_%d.csv' % bot_id) as f:
                retweeters = [line.strip('\n').split(',') for line in f.readlines()]
            retweeters.sort()
            with open(self.dir_name + '/likers_%d.csv' % bot_id) as f:
                likers = [line.strip('\n').split(',') for line in f.readlines()]
            likers.sort()

            num_rows = len(records)
            if (len(retweeters) != num_rows):
                print "Number of rows in records and retweeters do not match"
            elif (len(likers) != num_rows):
                print "Number of rows in records and likers do not match"

            # List of ID of tweets posted by bot
            list_tweet_ids = [ line[0] for line in records ]
            # List of tweet contents (text)
            list_tweets = bot.get_tweets(list_tweet_ids)
            list_pair_id_text = [ (tweet.id_str, tweet.text) for tweet in list_tweets ]
            list_pair_id_text.sort()

            for idx in range(0, num_rows):
                row = records[idx]
                tweet_id_str = row[0]
                pair = list_pair_id_text[idx]
                if tweet_id_str != pair[0]:
                    print "Tweet id mismatch!"
                    break
                else:
                    # Insert the text of tweet into the row
                    row.insert(1, pair[1].replace("\n", " "))

                # Insert bot id into first column
                row.insert(0, "%s" % bot_id)

                if retweeters[idx][0] != tweet_id_str:
                    print "Tweet id mismatch with retweeters!"
                    break
                else:
                    # Skip over the tweet id and final empty string
                    row = row + retweeters[idx][1:-1]
                if likers[idx][0] != tweet_id_str:
                    print "Tweet id mismatch with likers!"
                    break
                else:
                    # Skip over the tweet id and final empty string
                    row = row + likers[idx][1:-1]
                list_combined.append( row )
        # Sort by time of post
        list_combined.sort(key=lambda x: x[3])
        f = open(self.dir_name + "/%s" % outfile, 'w')
        for row in list_combined:
            str_row = "\t".join(row) + "\n"
            f.write(str_row.encode('utf8'))
        f.close()

                            
    def print_user_count(self):
        for key, value in self.map_user_count.iteritems():
            print key, value

    def print_user_response(self):
        for key, value in self.map_user_response.iteritems():
            print key, value

    def get_total_response(self):
        return self.total_response

    def get_num_active(self):
        return len(self.set_active)

    def get_num_active_response(self):
        return len(self.set_active_response)

    def get_total_activity(self):
        return self.total_activity

    def get_total_friends(self):
        return len(self.set_friends)

    
