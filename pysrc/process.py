import numpy as np
import pandas as pd
import lxml.etree as etree
import sqlite3 as sql
from tqdm.notebook import tqdm

__all__ = ['DB']

class DB:

    '''
        DB object to make manipulation cleaner. Creates connection and implements function
        to make access cleaner.

        Args:
            db_route: File route to db.sqlite file
    '''
    def __init__(self, db_route):
        self.db_route = db_route
        self.con = self.create_connection(self.db_route)
        self.match = self.getDF('Match')
        self.team = self.getDF('Team')
        self.team_attr = self.getDF('Team_Attributes')
        self.league = self.getDF('League')
        self.player = self.getDF('Player')

        self.match_team = self.joinMatchTeamDF()

    
    '''
        Creates SQL db connection to db.sqlite file
        Args:
            db_route: Route to db.sqlite file
        Returns:
            SQL connection, saves to class object
    '''
    def create_connection(self, db_route):
        return sql.connect(db_route)
        #df_match = pd.read_sql_query('SELECT * FROM Match', con)
        #df_team = pd.read_sql_query('SELECT * FROM Team', con)

    '''
        Creates Pandas Dataframe from SQL connection in db.sqlite file from requested name.
        Args:
            df_name: Name of table as it appears in sqlite
        Returns:
            Pandas dataframe of requested table
    '''
    def getDF(self, df_name):
        return pd.read_sql_query('SELECT * FROM %s' % df_name, self.con)

    def joinMatchTeamDF(self):
        columns = [
            'match_api_id','date',
            'home_team_api_id', 'away_team_api_id',
            'home_team_goal', 'away_team_goal',
            'foulcommit', 'card', 'corner'
        ]
        short_match = self.match.dropna(subset = ['foulcommit'])[columns]
        short_team = self.team[['team_api_id', 'team_long_name']]
        m1 = pd.merge(
            short_match, short_team,
            how = 'inner', left_on = 'home_team_api_id',
            right_on = 'team_api_id', suffixes = ("_x", "_y"))

        m2 = pd.merge(
            m1, short_team,
            how = 'inner', left_on = 'away_team_api_id',
            right_on = 'team_api_id', suffixes = ('_x', '_y'))


        m2 = m2.rename(columns = {
            'team_long_name_x' : 'home_team_name',
            'team_long_name_y' : 'away_team_name'
            }
        )

        final_columns = [
            'match_api_id', 'date',
            'home_team_api_id', 'home_team_name',
            'away_team_api_id', 'away_team_name',
            'home_team_goal', 'away_team_goal',
            'foulcommit', 'card', 'corner'
        ]

        return m2[final_columns]


    def unravelFoulDF(self, index):
        columns = ['subtype','team']
        xml = self.match_team['foulcommit'].iloc[index]
        match_id = self.match_team['match_api_id'].iloc[index]
        
        foul_df = None
        if xml != '<foulcommit />':
            foul_df = pd.read_xml(xml)
        else:
            return pd.DataFrame()

        for col in columns:
            if col not in foul_df.columns:
                foul_df[col] = [None] * foul_df.shape[0]

        foul_df = foul_df[columns]
        foul_df['match_id'] = [match_id] * foul_df.shape[0]

        foul_df = foul_df.rename(columns = {
            'subtype' : 'foul_reason',
            'team' : 'fouling_team'
        })

        return foul_df


    def stackFoulCardDF(self, custom_range = None):
        if custom_range == None:
            custom_range = range(self.match_team.shape[0])

        df_card = pd.concat(
            [pd.get_dummies(self.unravelCardDF(x), columns = ['card_color', 'card_reason']) for x in tqdm(custom_range, desc = 'Stacking Cards') if self.unravelCardDF(x).shape[0] > 0]
        ).groupby(by = ['match_id', 'carded_team'], as_index = False).sum()

        df_foul = pd.concat(
            [pd.get_dummies(self.unravelFoulDF(x), columns = ['foul_reason']) for x in tqdm(custom_range, desc = 'Stacking Fouls') if self.unravelFoulDF(x).shape[0] > 0]
        ).groupby(by = ['match_id', 'fouling_team'], as_index = False).sum()

        df = pd.merge(self.match_team, df_card, left_on = 'match_api_id', right_on = 'match_id').drop(['match_id'], axis = 1)
        df = pd.merge(df, df_foul, left_on = 'match_api_id', right_on = 'match_id').drop(['match_id'], axis = 1)
        df = df.drop(['foulcommit', 'card', 'corner'], axis = 1)
        
        return df


    def unravelCardDF(self, index):
        columns = [
            'match_id',
            'card_type',
            'subtype',
            'team'
        ]
        xml = self.match_team['card'].iloc[index]
        match_id = self.match_team['match_api_id'].iloc[index]
        
        card_df = None
        if xml != '<card />':
            card_df = pd.read_xml(xml)
        else:
            return pd.DataFrame()

        for col in columns:
            if col not in card_df.columns:
                card_df[col] = [None] * card_df.shape[0]

        card_df = card_df[columns]
        card_df['match_id'] = [match_id] * card_df.shape[0]

        card_df = card_df.rename(columns = {
            'subtype' : 'card_reason',
            'card_type' : 'card_color',
            'team' : 'carded_team'
        })

        return card_df




