# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import json

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

from google.api_core import protobuf_helpers

from .models import KeywordThemesRecommendations
from .serializers import KeywordThemesRecommendationsSerializer

def sc_settings(
    refresh_token, 
    customer_id, 
    campaign_id,
    use_login_id):
    '''
    Get the current settings of the campaign to show to the user
    '''
    # Configurations
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    GOOGLE_DEVELOPER_TOKEN = os.environ.get("GOOGLE_DEVELOPER_TOKEN", None)
    GOOGLE_LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_LOGIN_CUSTOMER_ID", None)

    # Configure using dictionary.
    # Check if we need to use login_customer_id in the headers,
    # which is needed if the Ads account was created by the app.
    if use_login_id == True:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        # "linked_customer_id": customer_id,
        "use_proto_plus": True}
    else:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        # "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        "linked_customer_id": customer_id,
        "use_proto_plus": True}

    client = GoogleAdsClient.load_from_dict(credentials)

    # to store the campaign settings
    campaign_settings = []
    data = {}

    # get the current campaign name, status, and performance metrics
    ga_service = client.get_service("GoogleAdsService")
    query = (f'''
    SELECT campaign.id, campaign.name, 
    campaign.status, metrics.impressions, metrics.clicks,
    metrics.all_conversions, metrics.all_conversions_value,
    metrics.interactions 
    FROM campaign 
    WHERE campaign.id = {campaign_id} ''')
    response = ga_service.search_stream(customer_id=customer_id, query=query)

    for batch in response:
        for row in batch.results:
            data["campaign_name"] = row.campaign.name
            data["campaign_id"] = row.campaign.id
            if row.campaign.status == 1:
                data["status"] = "Unspecified"
            elif row.campaign.status == 2:
                data["status"] = "Active"
            elif row.campaign.status == 3:
                data["status"] = "Paused"
            elif row.campaign.status == 4:
                data["status"] = "Removed"
            data["impressions"] = row.metrics.impressions
            data["interactions"] = row.metrics.interactions
            data["clicks"] = row.metrics.clicks
            data["conv"] = round(row.metrics.all_conversions, 0)
            data["conv_value"] = round(row.metrics.all_conversions_value, 0)
                
    # get the business name, landing page, phone number, language, and country
    query = (f'''
    SELECT campaign.id, smart_campaign_setting.business_name, 
    smart_campaign_setting.final_url, 
    smart_campaign_setting.phone_number.phone_number, 
    smart_campaign_setting.advertising_language_code,
    smart_campaign_setting.phone_number.country_code
    FROM smart_campaign_setting 
    WHERE campaign.id = {campaign_id} ''')
    response = ga_service.search_stream(customer_id=customer_id, query=query)

    for batch in response:
        for row in batch.results:
            data["business_name"] = row.smart_campaign_setting.business_name
            data["final_url"] = row.smart_campaign_setting.final_url
            data["phone_number"] = row.smart_campaign_setting.phone_number.phone_number
            data["language_code"] = row.smart_campaign_setting.advertising_language_code
            data["country_code"] = row.smart_campaign_setting.phone_number.country_code
    
    # get the current budget id and amount
   
    query = ('SELECT campaign.id, campaign_budget.id, campaign_budget.amount_micros '
    'FROM campaign_budget '
    'WHERE campaign.id = '+ campaign_id + ' ')
    response = ga_service.search_stream(customer_id=customer_id, query=query)

    for batch in response:
        for row in batch.results:
            data["budget_id"] = row.campaign_budget.id
            data["budget_micros"] = row.campaign_budget.amount_micros
    
    # get the resource_name and text assets (headlines and descriptions)
  
    query = (f'''
    SELECT campaign.id, ad_group_ad.ad.id,  
    ad_group_ad.ad.smart_campaign_ad.headlines, 
    ad_group_ad.ad.smart_campaign_ad.descriptions   
    FROM ad_group_ad 
    WHERE campaign.id = {campaign_id} ''')
    response = ga_service.search_stream(customer_id=customer_id, query=query)

    for batch in response:
        for row in batch.results:
            ad_id = row.ad_group_ad.ad.id
            ad_group_ad_text_ad_descriptions = row.ad_group_ad.ad.smart_campaign_ad.descriptions
            ad_group_ad_text_ad_headlines = row.ad_group_ad.ad.smart_campaign_ad.headlines

    data["ad_id"] = ad_id
    data["headline_1"] = ad_group_ad_text_ad_headlines[0].text
    data["headline_2"] = ad_group_ad_text_ad_headlines[1].text
    data["headline_3"] = ad_group_ad_text_ad_headlines[2].text
    data["desc_1"] = ad_group_ad_text_ad_descriptions[0].text
    data["desc_2"] = ad_group_ad_text_ad_descriptions[1].text

    # get resource_name of the ad using the ad_id
    ad_service = client.get_service("AdService")
    ad_resource_name = ad_service.ad_path(
        customer_id, ad_id
    )
    data["ad_resource_name"] = ad_resource_name

    # get the current geo location targets names

    # step 1: get the geo_target_constant's of the campaign_id and
    # their corresponding campaign_criterion_id
    # ga_service = client.get_service("GoogleAdsService")
    query = (f'''
    SELECT campaign.id, campaign_criterion.resource_name, campaign_criterion.criterion_id,  
    campaign_criterion.location.geo_target_constant
    FROM campaign_criterion 
    WHERE campaign.id = {campaign_id} ''')
    response = ga_service.search_stream(customer_id=customer_id, query=query)

    geo_target_constant_list = []
    campaign_criterion_id_list = []
    for batch in response:
        for row in batch.results:
            geo_target_constants = row.campaign_criterion.location.geo_target_constant
            # print('geo_target_constants:')
            # print(geo_target_constants) 
            if geo_target_constants:
                geo_target_constant_list.append(geo_target_constants)
                campaign_criterion_id_list.append(row.campaign_criterion.criterion_id)
            # campaign_criterion_id = row.campaign_criterion.criterion_id

    print('geo_target_constant_list:')
    print(geo_target_constant_list)
    print("campaign_criterion_id_list:")
    print(campaign_criterion_id_list)

    # step 2: get the geo_target_names
    geo_target_names = []
    for constants in geo_target_constant_list:

        # print(constants)    # constants = 'geoTargetConstants/20009'
        constants_id = constants.split('/')[1]  # get only the id
        # print(constants_id)
        
        query = (f'''
        SELECT geo_target_constant.name, geo_target_constant.id 
        FROM geo_target_constant 
        WHERE geo_target_constant.id = {constants_id} ''')
        response = ga_service.search_stream(customer_id=customer_id, query=query)
        
        for batch in response:
            for row in batch.results:
                geo_target_constant_name = row.geo_target_constant.name
                geo_target_names.append(geo_target_constant_name)

    # print('geo_target_names to show the user the current location targets:')
    # print(geo_target_names)
    data["geo_targets"] = geo_target_names

    # get the resource_name and display_name of the current keyword themes

    # step 1: fetch the resource name list of keyword_theme_constant
    query = (f'''
    SELECT campaign_criterion.type, campaign_criterion.status, 
    campaign_criterion.criterion_id, campaign_criterion.keyword_theme.keyword_theme_constant 
    FROM campaign_criterion 
    WHERE campaign_criterion.type = 'KEYWORD_THEME'
    AND campaign.id = {campaign_id}
    ''')
    response = ga_service.search_stream(customer_id=customer_id, query=query)

    keyword_theme_constant_list = []
    campaign_criterion_id_list = []
    for batch in response:
        for row in batch.results:
            if row.campaign_criterion.keyword_theme.keyword_theme_constant:
                keyword_theme_constant_list.append(
                    row.campaign_criterion.keyword_theme.keyword_theme_constant
                )
                campaign_criterion_id_list.append(
                    row.campaign_criterion.criterion_id
                )

    print("keyword_theme_constant_list:")
    print(keyword_theme_constant_list)
    

    # step 2: fetch the attributes of keyword_theme_constant based on resource name
    keyword_theme_display_name_list = []
    for i in keyword_theme_constant_list:
        query = (f'''
        SELECT keyword_theme_constant.resource_name, 
        keyword_theme_constant.display_name, 
        keyword_theme_constant.country_code 
        FROM keyword_theme_constant 
        WHERE keyword_theme_constant.resource_name = '{i}'
        ''')
        try:
            response = ga_service.search_stream(customer_id=customer_id, query=query)
            for batch in response:
                for row in batch.results:
                    keyword_theme_display_name_list.append(
                        row.keyword_theme_constant.display_name.title()
                        )
        except:
            None

    
    print("keyword_theme_display_name_list:")
    print(keyword_theme_display_name_list)

    # eliminate duplicates and add unique values only
    data["keyword_themes"] = list(dict.fromkeys(keyword_theme_display_name_list))

    # get current ad schedule settings
    query = (f'''
        SELECT 
            campaign.id, 
            campaign_criterion.ad_schedule.day_of_week, 
            campaign_criterion.ad_schedule.end_hour, 
            campaign_criterion.ad_schedule.start_hour,
            campaign_criterion.criterion_id
        FROM campaign_criterion 
        WHERE campaign.id = {campaign_id} 
        ''')
    googleads_service = client.get_service("GoogleAdsService")
    response = googleads_service.search_stream(
        customer_id=customer_id, 
        query=query)

    for batch in response:
        for row in batch.results:
            print(f"day_of_week: {row.campaign_criterion.ad_schedule.day_of_week}")
            if row.campaign_criterion.ad_schedule.day_of_week == 0:
                print("Ad Scheduled not configured for campaign.")
            else: 
                # the result will be in the format DayOfWeek.MONDAY so transform it
                day = str(row.campaign_criterion.ad_schedule.day_of_week).split('.')[1]
                # filter out those campaign criterion that are not ad schedule
                if day != 'UNSPECIFIED':
                    data[f'{day}'] = day
                    data[f'{day}_start_hour'] = row.campaign_criterion.ad_schedule.start_hour
                    data[f'{day}_end_hour'] = row.campaign_criterion.ad_schedule.end_hour

    # append all the data to the campaign_settings object
    campaign_settings.append(data)
    json.dumps(campaign_settings)

    return campaign_settings


def pause_sc(
    refresh_token, 
    customer_id, 
    campaign_id,
    use_login_id):
    '''
    Pause smart campaign - OK
    Parameters needed: credentials, customer_id, campaign_id
    '''

    # Configurations
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    GOOGLE_DEVELOPER_TOKEN = os.environ.get("GOOGLE_DEVELOPER_TOKEN", None)
    GOOGLE_LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_LOGIN_CUSTOMER_ID", None)

    # Configure using dictionary.
    # Check if we need to use login_customer_id in the headers,
    # which is needed if the Ads account was created by the app.
    if use_login_id == True:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        # "linked_customer_id": customer_id,
        "use_proto_plus": True}
    else:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        # "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        "linked_customer_id": customer_id,
        "use_proto_plus": True}

    client = GoogleAdsClient.load_from_dict(credentials)

    # start update mutate operation
    mutate_operation = client.get_type("MutateOperation")
    campaign = (
        mutate_operation.campaign_operation.update
    )

    # get CampaignService for the campaign_id
    campaign_service = client.get_service("CampaignService")
    campaign.resource_name = campaign_service.campaign_path(
        customer_id, campaign_id
    )

    # pause the campaign
    campaign.status = client.enums.CampaignStatusEnum.PAUSED

    # create field mask to update operation
    client.copy_from(
        mutate_operation.campaign_operation.update_mask,
        protobuf_helpers.field_mask(None, campaign._pb),
    )

    # get the service to use the mutate method
    ga_service = client.get_service("GoogleAdsService")

    # send the mutate request
    response = ga_service.mutate(
        customer_id=customer_id,
        mutate_operations=[
            mutate_operation,
        ],
    )

    print("response:")
    print(response)

    # get the new status to send it to the frontend
    query = ('SELECT campaign.id, campaign.status '
    'FROM campaign '
    'WHERE campaign.id = '+ campaign_id + ' ')
    response = ga_service.search_stream(customer_id=customer_id, query=query)
    
    status = []
    data = {}
    for batch in response:
        for row in batch.results:
            # get campaign status name
            # https://developers.google.com/google-ads/api/reference/rpc/v8/CampaignStatusEnum.CampaignStatus
            if row.campaign.status == 0:
                campaign_status = "Unspecified"
            elif row.campaign.status == 1: 
                campaign_status = "Unknown"
            elif row.campaign.status == 2:
                campaign_status = "Active"      # in Google's documentation they use 'Enabled' but 'Active' is more user-friendly
            elif row.campaign.status == 3:
                campaign_status = "Paused"
            elif row.campaign.status == 4:
                campaign_status = "Removed"
            
            data["new_status"] = campaign_status
            print('new_status:')
            print(campaign_status)

    status.append(data)
    json.dumps(status)

    print(status) 
    return status

def enable_sc(
    refresh_token, 
    customer_id, 
    campaign_id,
    use_login_id):
    '''
    Enable smart campaign - OK
    Parameters needed: credentials, customer_id, campaign_id
    '''
    # Configurations
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    GOOGLE_DEVELOPER_TOKEN = os.environ.get("GOOGLE_DEVELOPER_TOKEN", None)
    GOOGLE_LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_LOGIN_CUSTOMER_ID", None)

    # Configure using dictionary.
    # Check if we need to use login_customer_id in the headers,
    # which is needed if the Ads account was created by the app.
    if use_login_id == True:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        # "linked_customer_id": customer_id,
        "use_proto_plus": True}
    else:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        # "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        "linked_customer_id": customer_id,
        "use_proto_plus": True}

    client = GoogleAdsClient.load_from_dict(credentials)

    # start update mutate operation
    mutate_operation = client.get_type("MutateOperation")
    campaign = (
        mutate_operation.campaign_operation.update
    )

    # get CampaignService for the campaign_id
    campaign_service = client.get_service("CampaignService")
    campaign.resource_name = campaign_service.campaign_path(
        customer_id, campaign_id
    )

    # enable the campaign
    campaign.status = client.enums.CampaignStatusEnum.ENABLED

    # create field mask to update operation
    client.copy_from(
        mutate_operation.campaign_operation.update_mask,
        protobuf_helpers.field_mask(None, campaign._pb),
    )

    # get the service to use the mutate method
    ga_service = client.get_service("GoogleAdsService")

    # send the mutate request
    response = ga_service.mutate(
        customer_id=customer_id,
        mutate_operations=[
            mutate_operation,
        ],
    )
    
    print("response:")
    print(response)

    # get the new status to send it to the frontend
    query = ('SELECT campaign.id, campaign.status '
    'FROM campaign '
    'WHERE campaign.id = '+ campaign_id + ' ')
    response = ga_service.search_stream(customer_id=customer_id, query=query)
    
    status = []
    data = {}
    for batch in response:
        for row in batch.results:
            # get campaign status name
            # https://developers.google.com/google-ads/api/reference/rpc/v8/CampaignStatusEnum.CampaignStatus
            if row.campaign.status == 0:
                campaign_status = "Unspecified"
            elif row.campaign.status == 1: 
                campaign_status = "Unknown"
            elif row.campaign.status == 2:
                campaign_status = "Active"      # in Google's documentation they use 'Enabled' but 'Active' is more user-friendly
            elif row.campaign.status == 3:
                campaign_status = "Paused"
            elif row.campaign.status == 4:
                campaign_status = "Removed"
            
            data["new_status"] = campaign_status
            print('new_status:')
            print(campaign_status)

    status.append(data)
    json.dumps(status)

    print(status) 
    return status

def delete_sc(
    refresh_token, 
    customer_id, 
    campaign_id,
    use_login_id):
    '''
    Remove smart campaign - OK
    Parameters needed: credentials, customer_id, campaign_id
    '''
    # Configurations
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    GOOGLE_DEVELOPER_TOKEN = os.environ.get("GOOGLE_DEVELOPER_TOKEN", None)
    GOOGLE_LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_LOGIN_CUSTOMER_ID", None)

    # Configure using dictionary.
    # Check if we need to use login_customer_id in the headers,
    # which is needed if the Ads account was created by the app.
    if use_login_id == True:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        # "linked_customer_id": customer_id,
        "use_proto_plus": True}
    else:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        # "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        "linked_customer_id": customer_id,
        "use_proto_plus": True}

    client = GoogleAdsClient.load_from_dict(credentials)

    # get CampaignService for the campaign_id
    campaign_service = client.get_service("CampaignService")
    resource_name = campaign_service.campaign_path(customer_id, campaign_id)

    # get CampaignOperation to remove the resource (i.e., the campaign)
    campaign_operation = client.get_type("CampaignOperation")
    campaign_operation.remove = resource_name

    # send the remove operation
    response = campaign_service.mutate_campaigns(
    customer_id=customer_id, operations=[campaign_operation]
    )

    print("response:")
    print(response)

    # get the service to query the new status of the campaign
    ga_service = client.get_service("GoogleAdsService")

    # get the new status to send it to the frontend
    query = ('SELECT campaign.id, campaign.status '
    'FROM campaign '
    'WHERE campaign.id = '+ campaign_id + ' ')
    response = ga_service.search_stream(customer_id=customer_id, query=query)
    
    status = []
    data = {}
    for batch in response:
        for row in batch.results:
            # get campaign status name
            # https://developers.google.com/google-ads/api/reference/rpc/v8/CampaignStatusEnum.CampaignStatus
            if row.campaign.status == 0:
                campaign_status = "Unspecified"
            elif row.campaign.status == 1: 
                campaign_status = "Unknown"
            elif row.campaign.status == 2:
                campaign_status = "Active"      # in Google's documentation they use 'Enabled' but 'Active' is more user-friendly
            elif row.campaign.status == 3:
                campaign_status = "Paused"
            elif row.campaign.status == 4:
                campaign_status = "Removed"
            
            data["new_status"] = campaign_status
            print('new_status:')
            print(campaign_status)

    status.append(data)
    json.dumps(status)

    print(status) 
    return status

def edit_name_sc(
    refresh_token, 
    customer_id, 
    campaign_id, 
    new_campaign_name,
    use_login_id):
    '''
    Change name of smart campaign - OK
    Parameters needed: credentials, customer_id, campaign_id, new_campaign_name
    '''
    # Configurations
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    GOOGLE_DEVELOPER_TOKEN = os.environ.get("GOOGLE_DEVELOPER_TOKEN", None)
    GOOGLE_LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_LOGIN_CUSTOMER_ID", None)

    # Configure using dictionary.
    # Check if we need to use login_customer_id in the headers,
    # which is needed if the Ads account was created by the app.
    if use_login_id == True:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        # "linked_customer_id": customer_id,
        "use_proto_plus": True}
    else:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        # "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        "linked_customer_id": customer_id,
        "use_proto_plus": True}

    client = GoogleAdsClient.load_from_dict(credentials)

    # start update mutate operation
    mutate_operation = client.get_type("MutateOperation")
    campaign = (
        mutate_operation.campaign_operation.update
    )

    # get CampaignService for the campaign_id
    campaign_service = client.get_service("CampaignService")
    campaign.resource_name = campaign_service.campaign_path(
        customer_id, campaign_id
    )

    # change name of the campaign
    campaign.name = new_campaign_name

    # create field mask to update operation
    client.copy_from(
        mutate_operation.campaign_operation.update_mask,
        protobuf_helpers.field_mask(None, campaign._pb),
    )

    # get the service to use the mutate method
    ga_service = client.get_service("GoogleAdsService")

    # send the mutate request
    response = ga_service.mutate(
        customer_id=customer_id,
        mutate_operations=[
            mutate_operation,
        ],
    )
    
    print("response:")
    print(response)

    # get the new name to send it to the frontend
    query = ('SELECT campaign.id, campaign.name '
    'FROM campaign '
    'WHERE campaign.id = '+ campaign_id + ' ')
    response = ga_service.search_stream(customer_id=customer_id, query=query)

    name = []
    data = {}
    for batch in response:
        for row in batch.results:
            # get campaign name
            data["new_campaign_name"] = row.campaign.name
            
            print('new_campaign_name:')
            print(row.campaign.name)

    name.append(data)
    json.dumps(name)

    print(name) 
    return name

def edit_budget(
    refresh_token, 
    customer_id, 
    campaign_id, 
    new_budget, 
    budget_id,
    use_login_id):
    '''
    Edit budget of smart campaign - OK
    Parameters needed: credentials, customer_id, campaign_id, new_budget (in micros), budget_id
    '''
    # Configurations
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    GOOGLE_DEVELOPER_TOKEN = os.environ.get("GOOGLE_DEVELOPER_TOKEN", None)
    GOOGLE_LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_LOGIN_CUSTOMER_ID", None)

    # Configure using dictionary.
    # Check if we need to use login_customer_id in the headers,
    # which is needed if the Ads account was created by the app.
    if use_login_id == True:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        # "linked_customer_id": customer_id,
        "use_proto_plus": True}
    else:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        # "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        "linked_customer_id": customer_id,
        "use_proto_plus": True}

    client = GoogleAdsClient.load_from_dict(credentials)

    # start update mutate operation
    mutate_operation = client.get_type("MutateOperation")
    campaign_budget_operation = mutate_operation.campaign_budget_operation
    campaign_budget = campaign_budget_operation.update

    # set new budget amount
    campaign_budget.amount_micros = new_budget

    # use  the buget id for the CampaignBudgetservice to set the resource name of the campaign budget
    campaign_budget.resource_name = client.get_service(
        "CampaignBudgetService"
    ).campaign_budget_path(customer_id, budget_id)
    print('campaign_budget.resource_name:')
    print(campaign_budget.resource_name)

    # Retrieve a FieldMask for the fields configured in the campaign.
    client.copy_from(
        mutate_operation.campaign_budget_operation.update_mask,
        protobuf_helpers.field_mask(None, campaign_budget._pb),
    )
    print('campaign_budget_operation.update_mask:')
    print(campaign_budget_operation.update_mask)

    # get the service to use the mutate method
    ga_service = client.get_service("GoogleAdsService")

    # send the mutate request
    response = ga_service.mutate(
        customer_id=customer_id,
        mutate_operations=[
            mutate_operation,
        ],
    )
    
    print("response:")
    print(response)

    # get the new budget to send it to the frontend
    query = ('SELECT campaign.id, campaign_budget.id, campaign_budget.amount_micros '
    'FROM campaign_budget '
    'WHERE campaign.id = '+ campaign_id + ' ')
    response = ga_service.search_stream(customer_id=customer_id, query=query)

    budget = []
    data = {}
    for batch in response:
        for row in batch.results:
            data["budget_id"] = row.campaign_budget.id
            data["new_budget_micros"] = row.campaign_budget.amount_micros

    budget.append(data)
    json.dumps(budget)

    print(budget) 
    return budget

def edit_ad(
    refresh_token, 
    customer_id, 
    campaign_id, 
    new_headline_1, 
    new_headline_2, 
    new_headline_3, 
    new_desc_1,
    new_desc_2,
    use_login_id):
    '''
    Edit ad text - OK
    Parameters needed: credentials, customer_id, campaign_id, new_headline_1,
    new_headline_2, new_headline_3, new_desc_1, new_desc_2
    '''
    # Configurations
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    GOOGLE_DEVELOPER_TOKEN = os.environ.get("GOOGLE_DEVELOPER_TOKEN", None)
    GOOGLE_LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_LOGIN_CUSTOMER_ID", None)

    # Configure using dictionary.
    # Check if we need to use login_customer_id in the headers,
    # which is needed if the Ads account was created by the app.
    if use_login_id == True:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        # "linked_customer_id": customer_id,
        "use_proto_plus": True}
    else:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        # "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        "linked_customer_id": customer_id,
        "use_proto_plus": True}

    client = GoogleAdsClient.load_from_dict(credentials)

    # get the resource_name and text assets (headlines and descriptions)
    ga_service = client.get_service("GoogleAdsService")
    query = (f'''
    SELECT campaign.id, ad_group_ad.ad.id,  
    ad_group_ad.ad.smart_campaign_ad.headlines, 
    ad_group_ad.ad.smart_campaign_ad.descriptions  
    FROM ad_group_ad 
    WHERE campaign.id = {campaign_id} ''')
    response = ga_service.search_stream(customer_id=customer_id, query=query)

    for batch in response:
        for row in batch.results:
            ad_id = row.ad_group_ad.ad.id
            ad_group_ad_text_ad_descriptions = row.ad_group_ad.ad.smart_campaign_ad.descriptions
            ad_group_ad_text_ad_headlines = row.ad_group_ad.ad.smart_campaign_ad.headlines

    current_headline_1_user = ad_group_ad_text_ad_headlines[0].text
    current_headline_2_user = ad_group_ad_text_ad_headlines[1].text
    current_headline_3_user = ad_group_ad_text_ad_headlines[2].text
    print('current_headline_1_user:')
    print(current_headline_1_user)
    print('current_headline_2_user:')
    print(current_headline_2_user)
    print('current_headline_3_user:')
    print(current_headline_3_user)
    current_desc_1_user = ad_group_ad_text_ad_descriptions[0].text
    current_desc_2_user = ad_group_ad_text_ad_descriptions[1].text
    print('current_desc_1_user:')
    print(current_desc_1_user)
    print('current_desc_2_user:')
    print(current_desc_2_user)

    # get resource_name of the ad using the ad_id
    ad_service = client.get_service("AdService")
    ad_resource_name = ad_service.ad_path(
        customer_id, ad_id
    )
    print('ad_resource_name:')
    print(ad_resource_name)

    # start ad_operation that is used to mutate ads
    mutate_operation = client.get_type("MutateOperation")
    ad_operation = mutate_operation.ad_operation

    # set the resource to be updated
    ad = ad_operation.update
    ad.resource_name = ad_resource_name
    print('ad:')
    print(ad)

    # if new, set the new headlines
    if len(new_headline_1) != 0:
        headline_1 = client.get_type("AdTextAsset")
        headline_1.text = new_headline_1
    elif len(new_headline_1) == 0:
        headline_1 = client.get_type("AdTextAsset")
        headline_1.text = current_headline_1_user
    if len(new_headline_2) != 0:
        headline_2 = client.get_type("AdTextAsset")
        headline_2.text = new_headline_2
    elif len(new_headline_2) == 0:
        headline_2 = client.get_type("AdTextAsset")
        headline_2.text = current_headline_2_user
    if len(new_headline_3) != 0:
        headline_3 = client.get_type("AdTextAsset")
        headline_3.text = new_headline_3
    elif len(new_headline_3) == 0:
        headline_3 = client.get_type("AdTextAsset")
        headline_3.text = current_headline_3_user
    ad.smart_campaign_ad.headlines.extend([headline_1, headline_2, headline_3])

    # if new, set the new descriptions
    if len(new_desc_1) != 0:
        description_1 = client.get_type("AdTextAsset")
        description_1.text = new_desc_1
    elif len(new_desc_1) == 0:
        description_1 = client.get_type("AdTextAsset")
        description_1.text = current_desc_1_user
    if len(new_desc_2) != 0:
        description_2 = client.get_type("AdTextAsset")
        description_2.text = new_desc_2
    elif len(new_desc_2) == 0:
        description_2 = client.get_type("AdTextAsset")
        description_2.text = current_desc_2_user
    ad.smart_campaign_ad.descriptions.extend([description_1, description_2])

    print('new ad:')
    print(ad)

    # create a FieldMask for the fields updated in the ad and 
    # copy it to the ad_operation's update_mask field
    client.copy_from(
        mutate_operation.ad_operation.update_mask,
        protobuf_helpers.field_mask(None, ad._pb),
    )
    print('ad_operation.update_mask:')
    print(ad_operation.update_mask)


    response = ad_service.mutate_ads(
        customer_id = customer_id,
        operations = [
            ad_operation
        ],
    )

    print('response:')
    print(response)

    # get the new ad creative to send it to the frontend
    query = (f'''
    SELECT campaign.id, ad_group_ad.ad.id,  
    ad_group_ad.ad.smart_campaign_ad.headlines, 
    ad_group_ad.ad.smart_campaign_ad.descriptions  
    FROM ad_group_ad 
    WHERE campaign.id = {campaign_id} ''')
    response = ga_service.search_stream(customer_id=customer_id, query=query)

    for batch in response:
        for row in batch.results:
            ad_id = row.ad_group_ad.ad.id
            ad_group_ad_text_ad_descriptions = row.ad_group_ad.ad.smart_campaign_ad.descriptions
            ad_group_ad_text_ad_headlines = row.ad_group_ad.ad.smart_campaign_ad.headlines

    new_ad_creative = []
    data = {}
    data["new_head_1_api"] = ad_group_ad_text_ad_headlines[0].text
    data["new_head_2_api"] = ad_group_ad_text_ad_headlines[1].text
    data["new_head_3_api"] = ad_group_ad_text_ad_headlines[2].text
    data["new_desc_1_api"] = ad_group_ad_text_ad_descriptions[0].text
    data["new_desc_2_api"] = ad_group_ad_text_ad_descriptions[1].text
    new_ad_creative.append(data)
    json.dumps(new_ad_creative)
    print("new_ad_creative:")
    print(new_ad_creative)
    return new_ad_creative
   
def edit_keyword_themes(
    refresh_token, 
    customer_id, 
    campaign_id, 
    new_keywords_list,
    use_login_id
    ):
    '''
    Edit keyword themes - PARCIALLY OK
    Current bug doesn't let you query the keyword_themes (500 Internal error encountered).
    There is a workaround using the resource_name and fetching the data in two steps,
    but this doesn't solve for free_form_keyword_themes because they do not have
    resource_names.
    You will get the 500 internal server error if you try to query
    campaign_criterion.keyword_theme.free_form_keyword_theme
    '''
    # Configurations
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    GOOGLE_DEVELOPER_TOKEN = os.environ.get("GOOGLE_DEVELOPER_TOKEN", None)
    GOOGLE_LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_LOGIN_CUSTOMER_ID", None)

    # Configure using dictionary.
    # Check if we need to use login_customer_id in the headers,
    # which is needed if the Ads account was created by the app.
    if use_login_id == True:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        # "linked_customer_id": customer_id,
        "use_proto_plus": True}
    else:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        # "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        "linked_customer_id": customer_id,
        "use_proto_plus": True}

    client = GoogleAdsClient.load_from_dict(credentials)

    '''
    Step 1 - Get the resource names and display names of the current keyword themes
    '''
    ga_service = client.get_service("GoogleAdsService")

    # Step 1.1: fetch the resource name list of keyword_theme_constant
    query = (f'''
    SELECT campaign_criterion.type, campaign_criterion.status, 
    campaign_criterion.criterion_id, campaign_criterion.keyword_theme.keyword_theme_constant 
    FROM campaign_criterion 
    WHERE campaign_criterion.type = 'KEYWORD_THEME'
    AND campaign.id = {campaign_id}
    ''')
    response = ga_service.search_stream(customer_id=customer_id, query=query)

    keyword_theme_constant_list = []
    campaign_criterion_id_list = []
    for batch in response:
        for row in batch.results:
            if row.campaign_criterion.keyword_theme.keyword_theme_constant:
                keyword_theme_constant_list.append(
                    row.campaign_criterion.keyword_theme.keyword_theme_constant
                )
                campaign_criterion_id_list.append(
                    row.campaign_criterion.criterion_id
                )

    print("keyword_theme_constant_list:")
    print(keyword_theme_constant_list)

    # Step 1.2: fetch the attributes of keyword_theme_constant based on resource name
    keyword_theme_display_name_list = []
    for i in keyword_theme_constant_list:
        query = (f'''
        SELECT keyword_theme_constant.resource_name, 
        keyword_theme_constant.display_name, 
        keyword_theme_constant.country_code 
        FROM keyword_theme_constant 
        WHERE keyword_theme_constant.resource_name = '{i}'
        ''')
        try:
            response = ga_service.search_stream(customer_id=customer_id, query=query)
            for batch in response:
                for row in batch.results:
                    keyword_theme_display_name_list.append(row.keyword_theme_constant.display_name)
        except:
            None

    print("keyword_theme_display_name_list:")
    print(keyword_theme_display_name_list)

    '''
    Step 2 - Get the resource names of the new list of keyword themes 
    We are using this methodology as a workaround to the current bug in Google
    '''
    # use the display_name of list of new keyword themes 
    # to lookup for the keyword_theme_constant
    # in the KeywordThemesRecommendations model
    new_kt_constant_list = []
    print("new_keywords_list:")
    print(new_keywords_list)
    for display_name in new_keywords_list:
        try:
            # get the keyword_theme_constant
            kt_constant = KeywordThemesRecommendations.objects.get(display_name=display_name).resource_name
            # add it to the list
            new_kt_constant_list.append(kt_constant)
        except KeywordThemesRecommendations.DoesNotExist:
            print(f"{display_name} not found in model.")

    print("new_kt_constant_list:")
    print(new_kt_constant_list)
    ''''
    Step 3 - Create list of keywords to remove and to add
    '''
    kw_to_remove = []       # list of keyword constants to remove from campaign
    kw_to_remove_index = [] # this is used to identify the campaign_criterion_id
    kw_to_add = []          # list of keyword constants to add to the campaign

    print("start creating list of keywords to remove")
    for kw in keyword_theme_constant_list:
        print("kw:")
        print(kw)
        if kw not in new_kt_constant_list:
            kw_to_remove.append(kw)
            # get the index to use it later
            kw_to_remove_index.append(keyword_theme_constant_list.index(kw))

    print("start creating list of keywords to add")
    for kw in new_kt_constant_list:
        print("kw:")
        print(kw)
        if kw not in keyword_theme_constant_list:
            kw_info = client.get_type("KeywordThemeInfo")
            kw_info.keyword_theme_constant = kw
            kw_to_add.append(kw_info)

    print("kw_to_remove:")
    print(kw_to_remove)
    print("kw_to_add:")
    print(kw_to_add)

    '''
    Step 4 - Create remove and create operations
    '''
    # we are going to append all mutate operations under operations
    operations = []

    # get the campaign_criterion_id of those that we need to remove
    campaign_criterion_id_to_remove = []
    for i in kw_to_remove_index:
        campaign_criterion_id_to_remove.append(campaign_criterion_id_list[i])

    # create operation to remove them
    campaign_criterion_service = client.get_service("CampaignCriterionService")
    for i in campaign_criterion_id_to_remove:
        # get the resource name
        # that will be in this form: customers/{customer_id}/campaignCriteria/{campaign_id}~{criterion_id}
        campaign_criterion_resource_name = campaign_criterion_service.campaign_criterion_path(
        customer_id, campaign_id, i
        )
        # start mutate operation to remove
        mutate_operation = client.get_type("MutateOperation")
        campaign_criterion_operation = mutate_operation.campaign_criterion_operation
        campaign_criterion_operation.remove = campaign_criterion_resource_name
        operations.append(campaign_criterion_operation)

    # create operation to add keywords
    for kw in kw_to_add:
        mutate_operation = client.get_type("MutateOperation")
        campaign_criterion_operation = mutate_operation.campaign_criterion_operation

        campaign_criterion = campaign_criterion_operation.create

        # Set the campaign
        campaign_service = client.get_service("CampaignService")
        campaign_criterion.campaign = campaign_service.campaign_path(
            customer_id, campaign_id
        )
        # Set the criterion type to KEYWORD_THEME.
        campaign_criterion.type_ = client.enums.CriterionTypeEnum.KEYWORD_THEME
        # Set the keyword theme to the given KeywordThemeInfo.
        campaign_criterion.keyword_theme = kw
        operations.append(campaign_criterion_operation)

    print("operations to send as a mutate request:")
    print(operations)

    '''
    Step 5 - Send all mutate requests
    '''
    response = campaign_criterion_service.mutate_campaign_criteria(
        customer_id=customer_id,
        operations=[ 
            # Expand the list of campaign criterion operations into the list of
            # other mutate operations
            *operations,
        ],
    )
    print("response:")
    print(response)

    '''
    Step 6 - Query keyword themes to send to frontend
    '''
    # step 1: fetch the resource name list of keyword_theme_constant
    query = (f'''
    SELECT campaign_criterion.type, campaign_criterion.status, 
    campaign_criterion.criterion_id, campaign_criterion.keyword_theme.keyword_theme_constant 
    FROM campaign_criterion 
    WHERE campaign_criterion.type = 'KEYWORD_THEME'
    AND campaign.id = {campaign_id}
    ''')
    response = ga_service.search_stream(customer_id=customer_id, query=query)

    keyword_theme_constant_list = []
    campaign_criterion_id_list = []
    for batch in response:
        for row in batch.results:
            if row.campaign_criterion.keyword_theme.keyword_theme_constant:
                keyword_theme_constant_list.append(
                    row.campaign_criterion.keyword_theme.keyword_theme_constant
                )
                campaign_criterion_id_list.append(
                    row.campaign_criterion.criterion_id
                )

    print("keyword_theme_constant_list:")
    print(keyword_theme_constant_list)
    
    # step 2: fetch the attributes of keyword_theme_constant based on resource name
    keyword_theme_display_name_list = []
    for i in keyword_theme_constant_list:
        query = (f'''
        SELECT keyword_theme_constant.resource_name, 
        keyword_theme_constant.display_name, 
        keyword_theme_constant.country_code 
        FROM keyword_theme_constant 
        WHERE keyword_theme_constant.resource_name = '{i}'
        ''')
        try:
            response = ga_service.search_stream(customer_id=customer_id, query=query)
            for batch in response:
                for row in batch.results:
                    keyword_theme_display_name_list.append(
                        row.keyword_theme_constant.display_name.title()
                        )
        except:
            None

    
    print("keyword_theme_display_name_list:")
    print(keyword_theme_display_name_list)

    # eliminate duplicates and add unique values only
    updated_kw = list(dict.fromkeys(keyword_theme_display_name_list))

    json.dumps(updated_kw)

    return updated_kw

def edit_geo_targets(
    refresh_token,
    customer_id,
    campaign_id,
    new_geo_target_names,
    language_code,
    country_code,
    use_login_id):
    '''
    Edit geo location targeting - OK 
    Parameters needed: credentials, customer_id, campaign_id, new_geo_target_names
    '''

    '''
    Step 1 - Configurations
    '''

    # Configurations
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    GOOGLE_DEVELOPER_TOKEN = os.environ.get("GOOGLE_DEVELOPER_TOKEN", None)
    GOOGLE_LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_LOGIN_CUSTOMER_ID", None)

    # Configure using dictionary.
    # Check if we need to use login_customer_id in the headers,
    # which is needed if the Ads account was created by the app.
    if use_login_id == True:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        # "linked_customer_id": customer_id,
        "use_proto_plus": True}
    else:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        # "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        "linked_customer_id": customer_id,
        "use_proto_plus": True}

    client = GoogleAdsClient.load_from_dict(credentials)

    '''
    Step 2 - Get the current geo location target names
    '''
    print('start step 2 - Get the current geo location target names')
    # step 2.1: get the geo_target_constant's of the campaign_id and
    # their corresponding campaign_criterion_id
    ga_service = client.get_service("GoogleAdsService")
    query = (f'''
    SELECT campaign.id, campaign_criterion.resource_name, campaign_criterion.criterion_id,  
    campaign_criterion.location.geo_target_constant
    FROM campaign_criterion 
    WHERE campaign.id = {campaign_id} ''')
    response = ga_service.search_stream(customer_id=customer_id, query=query)

    geo_target_constant_list = []
    campaign_criterion_id_list = []
    for batch in response:
        for row in batch.results:
            geo_target_constants = row.campaign_criterion.location.geo_target_constant
            if geo_target_constants:
                geo_target_constant_list.append(geo_target_constants)
                campaign_criterion_id_list.append(row.campaign_criterion.criterion_id)

    print('geo_target_constant_list:')
    print(geo_target_constant_list)
    print("campaign_criterion_id_list:")
    print(campaign_criterion_id_list)

    # step 2.2: get the geo_target_names
    geo_target_names = []
    for constants in geo_target_constant_list:

        # print(constants)    # constants = 'geoTargetConstants/20009'
        constants_id = constants.split('/')[1]  # get only the id
        # print(constants_id)
        
        query = (f'''
        SELECT geo_target_constant.name, geo_target_constant.id 
        FROM geo_target_constant 
        WHERE geo_target_constant.id = {constants_id} ''')
        response = ga_service.search_stream(customer_id=customer_id, query=query)
        
        for batch in response:
            for row in batch.results:
                geo_target_constant_name = row.geo_target_constant.name
                geo_target_names.append(geo_target_constant_name)

    print('geo_target_names to show the user the current location targets:')
    print(geo_target_names)

    '''
    Step 3 - Create lists of geo targets to add and remove
    '''
    print('start step 3 - Create lists of geo targets to add and remove')
    # step 3.1: get geo target constants for the geo target names selected by user
    geo_targets = []
    for name in new_geo_target_names:

        gtc_service = client.get_service("GeoTargetConstantService")

        gtc_request = client.get_type("SuggestGeoTargetConstantsRequest")

        gtc_request.locale = language_code
        gtc_request.country_code = country_code
        # The location names to get suggested geo target constants.
        gtc_request.location_names.names.append(
            name
        )

        results = gtc_service.suggest_geo_target_constants(gtc_request)

        location_resource_names = []
        for suggestion in results.geo_target_constant_suggestions:
            geo_target_constant = suggestion.geo_target_constant
            
            location_resource_names.append(geo_target_constant.resource_name)

        # get the first one that is the one selected by the user
        geo_targets.append(location_resource_names[0])

    print('new geo_targets:')
    print(geo_targets)

    # step 3.2: create a list of geo_targets we need to remove and another list
    # of geo_targets that we need to add using create method
    geo_targets_to_remove = []
    geo_targets_to_remove_index = []
    geo_targets_to_add = []
    for targets in geo_targets:
        if targets not in geo_target_constant_list:
            geo_targets_to_add.append(targets)

    for targets in geo_target_constant_list:
        if targets not in geo_targets:
            geo_targets_to_remove.append(targets)
            # get the index to use it later
            geo_targets_to_remove_index.append(geo_target_constant_list.index(targets))


    print("geo_targets_to_add:")
    print(geo_targets_to_add)
    print("geo_targets_to_remove:")
    print(geo_targets_to_remove)
    print("geo_targets_to_remove_index:")
    print(geo_targets_to_remove_index)


    # step 3.3: get the LocationInfo type to set location targets as the API needs
    location_info_to_remove = []
    for location in geo_targets_to_remove:
        # Construct location information using the given geo target constant.
        location_info = client.get_type("LocationInfo")
        location_info.geo_target_constant = location
        location_info_to_remove.append(location_info)

    print('location_info_to_remove:')
    print(location_info_to_remove)

    location_info_to_add = []
    for location in geo_targets_to_add:
        # Construct location information using the given geo target constant.
        location_info = client.get_type("LocationInfo")
        location_info.geo_target_constant = location
        location_info_to_add.append(location_info)

    print('location_info_to_add:')
    print(location_info_to_add)

    '''
    Step 4 - Create the remove and create operation
    Important: update method does not work,
    so you will have to use remove and create
    to edit geo location targets.
    '''
    print('start step 4 - Create the remove and create operation')
    # we are going to append all mutate operations under operations
    operations = []

    # step 4.1: create remove operation

    # get the campaign_criterion_id of those that we need to remove
    campaign_criterion_id_to_remove = []
    for i in geo_targets_to_remove_index:
        campaign_criterion_id_to_remove.append(campaign_criterion_id_list[i])

    # create operation to remove them
    campaign_criterion_service = client.get_service("CampaignCriterionService")
    for i in campaign_criterion_id_to_remove:
        # get the resource name
        # that will be in this form: customers/{customer_id}/campaignCriteria/{campaign_id}~{criterion_id}
        campaign_criterion_resource_name = campaign_criterion_service.campaign_criterion_path(
        customer_id, campaign_id, i
        )
        # start mutate operation to remove
        mutate_operation = client.get_type("MutateOperation")
        campaign_criterion_operation = mutate_operation.campaign_criterion_operation
        campaign_criterion_operation.remove = campaign_criterion_resource_name
        operations.append(campaign_criterion_operation)

    # step 4.2: create the create operation
    for location in location_info_to_add:
        mutate_operation = client.get_type("MutateOperation")
        campaign_criterion_operation = mutate_operation.campaign_criterion_operation

        campaign_criterion = campaign_criterion_operation.create

        # Set the campaign
        campaign_service = client.get_service("CampaignService")
        campaign_criterion.campaign = campaign_service.campaign_path(
            customer_id, campaign_id
        )
        # Set the criterion type to LOCATION.
        campaign_criterion.type_ = client.enums.CriterionTypeEnum.LOCATION
        # Set the location to the given location.
        campaign_criterion.location = location
        operations.append(campaign_criterion_operation)

    print("operations to send as a mutate request:")
    print(operations)

    '''
    Step 5 - Send the mutate request
    '''
    print('start step 5 - Send the mutate request')
    response = campaign_criterion_service.mutate_campaign_criteria(
        customer_id=customer_id,
        operations=[ 
            # Expand the list of campaign criterion operations into the list of
            # other mutate operations
            *operations,
        ],
    )
    print("response:")
    print(response)

    '''
    Step 6 - Get new geo location targets
    '''
    print('start step 6 - Get new geo location targets')
    # step 6.1: get the geo_target_constant's of the campaign_id and
    # their corresponding campaign_criterion_id
    ga_service = client.get_service("GoogleAdsService")
    query = (f'''
    SELECT campaign.id, campaign_criterion.resource_name, campaign_criterion.criterion_id,  
    campaign_criterion.location.geo_target_constant
    FROM campaign_criterion 
    WHERE campaign.id = {campaign_id} ''')
    response = ga_service.search_stream(customer_id=customer_id, query=query)

    geo_target_constant_list = []
    campaign_criterion_id_list = []
    for batch in response:
        for row in batch.results:
            geo_target_constants = row.campaign_criterion.location.geo_target_constant
            if geo_target_constants:
                geo_target_constant_list.append(geo_target_constants)
                campaign_criterion_id_list.append(row.campaign_criterion.criterion_id)

    print('geo_target_constant_list:')
    print(geo_target_constant_list)
    print("campaign_criterion_id_list:")
    print(campaign_criterion_id_list)

    # step 6.2: get the geo_target_names
    geo_target_names = []
    for constants in geo_target_constant_list:

        # print(constants)    # constants = 'geoTargetConstants/20009'
        constants_id = constants.split('/')[1]  # get only the id
        # print(constants_id)
        
        query = (f'''
        SELECT geo_target_constant.name, geo_target_constant.id 
        FROM geo_target_constant 
        WHERE geo_target_constant.id = {constants_id} ''')
        response = ga_service.search_stream(customer_id=customer_id, query=query)
        
        for batch in response:
            for row in batch.results:
                geo_target_constant_name = row.geo_target_constant.name
                geo_target_names.append(geo_target_constant_name)

    print('geo_target_names to show the user the current location targets:')
    print(geo_target_names)

    json.dumps(geo_target_names)

    return(geo_target_names)

def edit_ad_schedule(
    refresh_token, 
    customer_id, 
    campaign_id, 
    mon_start,
    mon_end,
    tue_start,
    tue_end,
    wed_start,
    wed_end,
    thu_start,
    thu_end,
    fri_start,
    fri_end,
    sat_start,
    sat_end,
    sun_start,
    sun_end,
    use_login_id
    ):
    '''
    Step 1 - Configurations
    '''

    # Configurations
    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    GOOGLE_DEVELOPER_TOKEN = os.environ.get("GOOGLE_DEVELOPER_TOKEN", None)
    GOOGLE_LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_LOGIN_CUSTOMER_ID", None)

    # Configure using dictionary.
    # Check if we need to use login_customer_id in the headers,
    # which is needed if the Ads account was created by the app.
    if use_login_id == True:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        # "linked_customer_id": customer_id,
        "use_proto_plus": True}
    else:
        credentials = {
        "developer_token": GOOGLE_DEVELOPER_TOKEN,
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        # "login_customer_id": GOOGLE_LOGIN_CUSTOMER_ID,
        "linked_customer_id": customer_id,
        "use_proto_plus": True}

    client = GoogleAdsClient.load_from_dict(credentials)

    '''
    Step 2 - Get the criterion_id for those days that need to change.
    '''
    query = (f'''
    SELECT 
        campaign.id, 
        campaign_criterion.ad_schedule.day_of_week, 
        campaign_criterion.ad_schedule.end_hour, 
        campaign_criterion.ad_schedule.start_hour,
        campaign_criterion.criterion_id
    FROM campaign_criterion 
    WHERE campaign.id = {campaign_id} 
    ''')
    googleads_service = client.get_service("GoogleAdsService")
    response = googleads_service.search_stream(
        customer_id=customer_id, 
        query=query)

    current_ad_schedule = []
    current_campaign_criterion_id = []
    data = {}
    for batch in response:
        for row in batch.results:
            # the result will be in the format DayOfWeek.MONDAY so transform it
            day = str(row.campaign_criterion.ad_schedule.day_of_week).split('.')[1]
            # filter out those campaign criterion that are not ad schedule
            if day != 'UNSPECIFIED':
                data[f'{day}'] = day
                data[f'{day}_start_hour'] = row.campaign_criterion.ad_schedule.start_hour
                data[f'{day}_end_hour'] = row.campaign_criterion.ad_schedule.end_hour
                current_ad_schedule.append(data)
                # append criterion_id of those days that need change
                if day=="MONDAY" and (mon_start != -1 or mon_end != -1):
                    current_campaign_criterion_id.append(
                        row.campaign_criterion.criterion_id
                        )
                if day=="TUESDAY" and (tue_start != -1 or tue_end != -1):
                    current_campaign_criterion_id.append(
                        row.campaign_criterion.criterion_id
                        )
                if day=="WEDNESDAY" and (wed_start != -1 or wed_end != -1):
                    current_campaign_criterion_id.append(
                        row.campaign_criterion.criterion_id
                        )
                if day=="THURSDAY" and (thu_start != -1 or thu_end != -1):
                    current_campaign_criterion_id.append(
                        row.campaign_criterion.criterion_id
                        )
                if day=="FRIDAY" and (fri_start != -1 or fri_end != -1):
                    current_campaign_criterion_id.append(
                        row.campaign_criterion.criterion_id
                        )
                if day=="SATURDAY" and (sat_start != -1 or sat_end != -1):
                    current_campaign_criterion_id.append(
                        row.campaign_criterion.criterion_id
                        )
                if day=="SUNDAY" and (sun_start != -1 or sun_end != -1):
                    current_campaign_criterion_id.append(
                        row.campaign_criterion.criterion_id
                        )
    print("current_ad_schedule:")
    print(current_ad_schedule)

    '''
    Step 3 - Remove current ad schedule settings for the days that had changes.
    '''
    operations = []     # object that will contain all ad schedule operations (create & remove)
    # create operation to remove them
    campaign_criterion_service = client.get_service("CampaignCriterionService")
    for i in current_campaign_criterion_id:
        # get the resource name
        # that will be in this form: customers/{customer_id}/campaignCriteria/{campaign_id}~{criterion_id}
        campaign_criterion_resource_name = campaign_criterion_service.campaign_criterion_path(
        customer_id, campaign_id, i
        )
        # start mutate operation to remove
        mutate_operation = client.get_type("MutateOperation")
        campaign_criterion_operation = mutate_operation.campaign_criterion_operation
        campaign_criterion_operation.remove = campaign_criterion_resource_name
        operations.append(mutate_operation)

    '''
    Step 4 - Create Campaign Criterion for Ad Schedule of those days that need change.
    AdSchedule is specified as the day of the week and 
    a time interval within which ads will be shown.
    '''

    '''
    Step 4.1 - MONDAY
    '''
    if mon_start != -1 or mon_end != -1:
        mutate_operation = client.get_type("MutateOperation")
        campaign_criterion_operation = mutate_operation.campaign_criterion_operation

        campaign_criterion = campaign_criterion_operation.create

        # Set the campaign
        campaign_service = client.get_service("CampaignService")
        campaign_criterion.campaign = campaign_service.campaign_path(
            customer_id, campaign_id
        )
        # Set the criterion type to AD_SCHEDULE.
        campaign_criterion.type_ = client.enums.CriterionTypeEnum.AD_SCHEDULE
        # Get AdScheduleInfo object for MONDAY.
        ad_schedule_info = client.get_type("AdScheduleInfo")
        ad_schedule_info.day_of_week = client.enums.DayOfWeekEnum.MONDAY
        # check if user changed start hour (-1 means user did not change it)
        if mon_start != -1:
            ad_schedule_info.start_hour = mon_start
        else: ad_schedule_info.start_hour = data['MONDAY_start_hour']
        if mon_end != -1:
            ad_schedule_info.end_hour = mon_end
        else: ad_schedule_info.end_hour = data['MONDAY_end_hour']
        zero_minute_of_hour = client.enums.MinuteOfHourEnum.ZERO
        ad_schedule_info.start_minute = zero_minute_of_hour
        ad_schedule_info.end_minute = zero_minute_of_hour
        # Set the ad_schedule to the given ad_schedule.
        campaign_criterion.ad_schedule = ad_schedule_info
        operations.append(mutate_operation)
    '''
    Step 4.2 - TUESDAY
    '''
    if tue_start != -1 or tue_end != -1:
        mutate_operation = client.get_type("MutateOperation")
        campaign_criterion_operation = mutate_operation.campaign_criterion_operation

        campaign_criterion = campaign_criterion_operation.create

        # Set the campaign
        campaign_service = client.get_service("CampaignService")
        campaign_criterion.campaign = campaign_service.campaign_path(
            customer_id, campaign_id
        )
        # Set the criterion type to AD_SCHEDULE.
        campaign_criterion.type_ = client.enums.CriterionTypeEnum.AD_SCHEDULE
        # Get AdScheduleInfo object for TUESDAY.
        ad_schedule_info = client.get_type("AdScheduleInfo")
        ad_schedule_info.day_of_week = client.enums.DayOfWeekEnum.TUESDAY
        # check if user changed start hour (-1 means user did not change it)
        if tue_start != -1:
            ad_schedule_info.start_hour = tue_start
        else: ad_schedule_info.start_hour = data['TUESDAY_start_hour']
        if tue_end != -1:
            ad_schedule_info.end_hour = tue_end
        else: ad_schedule_info.end_hour = data['TUESDAY_end_hour']
        zero_minute_of_hour = client.enums.MinuteOfHourEnum.ZERO
        ad_schedule_info.start_minute = zero_minute_of_hour
        ad_schedule_info.end_minute = zero_minute_of_hour
        # Set the ad_schedule to the given ad_schedule.
        campaign_criterion.ad_schedule = ad_schedule_info
        operations.append(mutate_operation)
    '''
    Step 4.3 - WEDNESDAY
    '''
    if wed_start != -1 or wed_end != -1:
        mutate_operation = client.get_type("MutateOperation")
        campaign_criterion_operation = mutate_operation.campaign_criterion_operation

        campaign_criterion = campaign_criterion_operation.create

        # Set the campaign
        campaign_service = client.get_service("CampaignService")
        campaign_criterion.campaign = campaign_service.campaign_path(
            customer_id, campaign_id
        )
        # Set the criterion type to AD_SCHEDULE.
        campaign_criterion.type_ = client.enums.CriterionTypeEnum.AD_SCHEDULE
        # Get AdScheduleInfo object for WEDNESDAY.
        ad_schedule_info = client.get_type("AdScheduleInfo")
        ad_schedule_info.day_of_week = client.enums.DayOfWeekEnum.WEDNESDAY
        # check if user changed start hour (-1 means user did not change it)
        if wed_start != -1:
            ad_schedule_info.start_hour = wed_start
        else: ad_schedule_info.start_hour = data['WEDNESDAY_start_hour']
        if wed_end != -1:
            ad_schedule_info.end_hour = wed_end
        else: ad_schedule_info.end_hour = data['WEDNESDAY_end_hour']
        zero_minute_of_hour = client.enums.MinuteOfHourEnum.ZERO
        ad_schedule_info.start_minute = zero_minute_of_hour
        ad_schedule_info.end_minute = zero_minute_of_hour
        # Set the ad_schedule to the given ad_schedule.
        campaign_criterion.ad_schedule = ad_schedule_info
        operations.append(mutate_operation)
    '''
    Step 4.4 - THURSDAY
    '''
    if thu_start != -1 or thu_end != -1:
        mutate_operation = client.get_type("MutateOperation")
        campaign_criterion_operation = mutate_operation.campaign_criterion_operation

        campaign_criterion = campaign_criterion_operation.create

        # Set the campaign
        campaign_service = client.get_service("CampaignService")
        campaign_criterion.campaign = campaign_service.campaign_path(
            customer_id, campaign_id
        )
        # Set the criterion type to AD_SCHEDULE.
        campaign_criterion.type_ = client.enums.CriterionTypeEnum.AD_SCHEDULE
        # Get AdScheduleInfo object for THURSDAY.
        ad_schedule_info = client.get_type("AdScheduleInfo")
        ad_schedule_info.day_of_week = client.enums.DayOfWeekEnum.THURSDAY
        # check if user changed start hour (-1 means user did not change it)
        if thu_start != -1:
            ad_schedule_info.start_hour = thu_start
        else: ad_schedule_info.start_hour = data['THURSDAY_start_hour']
        if thu_end != -1:
            ad_schedule_info.end_hour = thu_end
        else: ad_schedule_info.end_hour = data['THURSDAY_end_hour']
        zero_minute_of_hour = client.enums.MinuteOfHourEnum.ZERO
        ad_schedule_info.start_minute = zero_minute_of_hour
        ad_schedule_info.end_minute = zero_minute_of_hour
        # Set the ad_schedule to the given ad_schedule.
        campaign_criterion.ad_schedule = ad_schedule_info
        operations.append(mutate_operation)
    '''
    Step 4.5 - FRIDAY
    '''
    if fri_start != -1 or fri_end != -1:
        mutate_operation = client.get_type("MutateOperation")
        campaign_criterion_operation = mutate_operation.campaign_criterion_operation

        campaign_criterion = campaign_criterion_operation.create

        # Set the campaign
        campaign_service = client.get_service("CampaignService")
        campaign_criterion.campaign = campaign_service.campaign_path(
            customer_id, campaign_id
        )
        # Set the criterion type to AD_SCHEDULE.
        campaign_criterion.type_ = client.enums.CriterionTypeEnum.AD_SCHEDULE
        # Get AdScheduleInfo object for FRIDAY.
        ad_schedule_info = client.get_type("AdScheduleInfo")
        ad_schedule_info.day_of_week = client.enums.DayOfWeekEnum.FRIDAY
        # check if user changed start hour (-1 means user did not change it)
        if fri_start != -1:
            ad_schedule_info.start_hour = fri_start
        else: ad_schedule_info.start_hour = data['FRIDAY_start_hour']
        if fri_end != -1:
            ad_schedule_info.end_hour = fri_end
        else: ad_schedule_info.end_hour = data['FRIDAY_end_hour']
        zero_minute_of_hour = client.enums.MinuteOfHourEnum.ZERO
        ad_schedule_info.start_minute = zero_minute_of_hour
        ad_schedule_info.end_minute = zero_minute_of_hour
        # Set the ad_schedule to the given ad_schedule.
        campaign_criterion.ad_schedule = ad_schedule_info
        operations.append(mutate_operation)
    '''
    Step 4.6 - SATURDAY
    '''
    if sat_start != -1 or sat_end != -1:
        mutate_operation = client.get_type("MutateOperation")
        campaign_criterion_operation = mutate_operation.campaign_criterion_operation

        campaign_criterion = campaign_criterion_operation.create

        # Set the campaign
        campaign_service = client.get_service("CampaignService")
        campaign_criterion.campaign = campaign_service.campaign_path(
            customer_id, campaign_id
        )
        # Set the criterion type to AD_SCHEDULE.
        campaign_criterion.type_ = client.enums.CriterionTypeEnum.AD_SCHEDULE
        # Get AdScheduleInfo object for SATURDAY.
        ad_schedule_info = client.get_type("AdScheduleInfo")
        ad_schedule_info.day_of_week = client.enums.DayOfWeekEnum.SATURDAY
        # check if user changed start hour (-1 means user did not change it)
        if sat_start != -1:
            ad_schedule_info.start_hour = sat_start
        else: ad_schedule_info.start_hour = data['SATURDAY_start_hour']
        if sat_end != -1:
            ad_schedule_info.end_hour = sat_end
        else: ad_schedule_info.end_hour = data['SATURDAY_end_hour']
        zero_minute_of_hour = client.enums.MinuteOfHourEnum.ZERO
        ad_schedule_info.start_minute = zero_minute_of_hour
        ad_schedule_info.end_minute = zero_minute_of_hour
        # Set the ad_schedule to the given ad_schedule.
        campaign_criterion.ad_schedule = ad_schedule_info
        operations.append(mutate_operation)
    '''
    Step 4.7 - SUNDAY
    '''
    if sun_start != -1 or sun_end != -1:
        mutate_operation = client.get_type("MutateOperation")
        campaign_criterion_operation = mutate_operation.campaign_criterion_operation

        campaign_criterion = campaign_criterion_operation.create

        # Set the campaign
        campaign_service = client.get_service("CampaignService")
        campaign_criterion.campaign = campaign_service.campaign_path(
            customer_id, campaign_id
        )
        # Set the criterion type to AD_SCHEDULE.
        campaign_criterion.type_ = client.enums.CriterionTypeEnum.AD_SCHEDULE
        # Get AdScheduleInfo object for SUNDAY.
        ad_schedule_info = client.get_type("AdScheduleInfo")
        ad_schedule_info.day_of_week = client.enums.DayOfWeekEnum.SUNDAY
        # check if user changed start hour (-1 means user did not change it)
        if sun_start != -1:
            ad_schedule_info.start_hour = sun_start
        else: ad_schedule_info.start_hour = data['SUNDAY_start_hour']
        if sun_end != -1:
            ad_schedule_info.end_hour = sun_end
        else: ad_schedule_info.end_hour = data['SUNDAY_end_hour']
        zero_minute_of_hour = client.enums.MinuteOfHourEnum.ZERO
        ad_schedule_info.start_minute = zero_minute_of_hour
        ad_schedule_info.end_minute = zero_minute_of_hour
        # Set the ad_schedule to the given ad_schedule.
        campaign_criterion.ad_schedule = ad_schedule_info
        operations.append(mutate_operation)

    '''
    Step 5 - Send the mutate operations
    '''
    googleads_service = client.get_service("GoogleAdsService")

    print("operations:")
    print(operations)
    # Send the operations into a single Mutate request.
    response = googleads_service.mutate(
        customer_id=customer_id,
        mutate_operations=[*operations]
    )

    '''
    Step 6 - Get updated ad schedule settings
    '''
    query = (f'''
    SELECT 
        campaign.id, 
        campaign_criterion.ad_schedule.day_of_week, 
        campaign_criterion.ad_schedule.end_hour, 
        campaign_criterion.ad_schedule.start_hour
    FROM campaign_criterion 
    WHERE campaign.id = {campaign_id} 
    ''')
    response = googleads_service.search_stream(
        customer_id=customer_id, 
        query=query)

    new_ad_schedule = []
    data = {}
    for batch in response:
        for row in batch.results:
            # the result will be in the format DayOfWeek.MONDAY so transform it
            day = str(row.campaign_criterion.ad_schedule.day_of_week).split('.')[1]
            # filter out those campaign criterion that are not ad schedule
            if day != 'UNSPECIFIED':
                data[f'{day}'] = day
                data[f'{day}_start_hour'] = row.campaign_criterion.ad_schedule.start_hour
                data[f'{day}_end_hour'] = row.campaign_criterion.ad_schedule.end_hour
                
    new_ad_schedule.append(data)
    json.dumps(new_ad_schedule)
    print("new_ad_schedule:")
    print(new_ad_schedule)

    return new_ad_schedule