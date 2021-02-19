#!/usr/bin/python3

import asyncio
import json
import aio_pika
import hashlib
import concurrent.futures
from rejson import Client, Path

async def key_generator(data):
    default='_d'

    # extract resource-group from the data packet

    data_json=json.loads(data)
    res_id=data_json['id']
    rg=res_id.split('/')[3]
    
    # Check if _rg is present in rg_dict{}

    if rg in rg_dict.keys():
        print('> RG is present.')
        # encode SHA1 of resource-id

        sha_id = hashlib.sha1(res_id.encode())
        attribute=rg_dict[rg]
        path_param=sha_rg.hexdigest()+'_'+data_json[attribute]
    else:
        print('> RG is not present.')
        path_param=sha_rg.hexdigest()+default
    
    return {'key': rg, 'path_param': path_param, 'data': data} 

async def insert_into_redis(client, data):
    print('> redis_key: '+key+' redis_path_param: '+path_param)
    # this needs to be tested
    some_test_data_id = data['data']['id']
    client.jsonset(data['key'],Path.rootPath(),json.dumps({}))
    client.jsonset(data['key'],data['path_param'],data['data'])
    
    if (json.loads(client.jsonget(data['key'],data['path_param']))['id']
            == some_test_data):
        return 'success'
    else:
        return 'failed'

async def main_loop(loop):
    
    # load the dictionary using the config file
    with open('rg_list.json') as rg_json_f:
        rg_dict=json.load(rg_json_f)
    print('> RG is loaded: ' + rg_dict)

    # Connect to Redis client
    
    redis_client=Client(host='redis-server',port=6379,decode_responses=True)

    # Connect to RabbitMQ
    # Can use connection pool instead of two separate clients
    rmq_pub_client = await aio_pika.connect_robust(
        "amqp://whatever_url_to_connect", loop=loop
    )

    # rmq_sub_client = await aio_pika.connect_robust(
    #    "amqp://whatever_url_to_connect", loop=loop
    # )
    
    rmq_q_name = "latest"
    redis_q_name = "redis-ingestion-queue"
    routing_key = "latest-data-for-redis"
    async with rmq_pub_client:
        channel = await rmq_pub_client.channel()
        queue_rmq = await channel.declare_queue(rmq_q_name, auto_delete=True)
        queue_redis = await channel.declare_queue(redis_q_name, auto_delete=True)
        
        # declare an exchange to push {data} generated by Key generator for consumption by redis_queue
        latest_exchange = await channel.declare_exchange("direct", auto_delete=True)
        
        # bind this latest_exchange to redis_queue
        await queue_redis.bind(latest_exchange, routing_key)

        async with queue_rmq.iterator() as queue_iter_1:
            async for message1 in queue_iter_1:
                async with message1.process():
                    
                    # call key_generator(message1.body())[using Futures implementation]
                    with concurrent.futures.ProcessPoolExecutor() as pool:
                        result = await loop.run_in_executor(
                                pool, key_generator(rmq_pub_client,message1.body()))
                        
                        # insert result to a default exchange? or use a separate exchange?
                        await channel.default_exchange.publish(
                                aio.pika.Message(body=result,routing_key=routing_key))  


   # async with rmq_sub_client:
        # channel = await rmq_sub_client.channel()
        
        # pull from the queue_redis and call insert_into_redis [using Futures implementation]
        # redis-ingestion-queue has to be bound to the aforementioend exchange 
        async with queue_redis.iterator() as queue_iter_2:
            async for message2 in queue_iter_2:
                async with message2.process():

                    # call insert_into_redis(message2.body())[using Futures implementation]
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        result = await loop.run_in_executor(
                                pool, insert_into_redis(redis_client,message2.body()))

                        # Surround with a try catch block?
                        # remove print and use logs instead
                        if result is not None and result == 'success':
                            print('Insertion was successful.')
                        else:
                            print('Insertion failed!')

    # return rmq_pub_client, redis_client

if '__name__' == '__main__':
    print('> Running Redis Client.')

    # write the asyncio part
    loop=asyncio.get_event_loop()
    loop.run(main(loop))
    # rmq_con, redis_con = loop.run(main_loop(loop))
    # 
    # try:
    #     loop.run_forever()
    # finally:
    #     # close connections
    #     loop.run_until_complete(rmq_con.close())
    #     # loop.run_until_complete(redis_con.close())


