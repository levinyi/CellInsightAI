import json
import uuid
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from asyncio import sleep
from datetime import datetime

class TaskConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()
        task_id = self.scope['url_route']['kwargs'].get('id', 'demo')
        self.group_name = f"task_{task_id}"
        
        # Join group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        # Only simulate for demo tasks
        if task_id == 'demo':
            # 模拟推送若干阶段事件
            for i in range(5):
                await sleep(0.8)
                await self.send_json({
                    'ts': datetime.utcnow().isoformat() + 'Z',
                    'phase': ['QC','HVG','PCA','UMAP','CLUSTER'][i],
                    'progress': int((i+1)/5*100),
                    'message': '阶段运行中',
                    'metrics': {
                        'cells': 10000 - i*123,
                        'doublet_rate': round(0.05 + i*0.005, 3),
                        'high_mito': round(0.12 - i*0.01, 3)
                    } if i%2==0 else None
                })
            await self.send_json({
                'ts': datetime.utcnow().isoformat() + 'Z',
                'phase': 'DONE',
                'progress': 100,
                'message': 'SUCCEEDED'
            })
            await self.close()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def task_message(self, event):
        """Handle task.message from group_send"""
        await self.send_json(event['payload'])