import { useState } from 'react';
import { MapPin, Clock, CreditCard, RefreshCw, Camera, Star } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';

export function RouteNavigationTab() {
  const [departure, setDeparture] = useState('홍대입구역');
  const [destination, setDestination] = useState('강남역');

  const routeResults = {
    duration: '45분',
    fare: '1,570원',
    transfers: '1회'
  };

  const foodRecommendations = [
    {
      id: 1,
      name: '황생가칼국수',
      location: '신촌역 1번 출구',
      type: '따뜻한 국물',
      rating: 4.6,
      detourTime: '+ 5분',
      tags: ['따뜻함', '국물', '면']
    },
    {
      id: 2,
      name: '이태원 분식',
      location: '이태원역 3번 출구',
      type: '간식',
      rating: 4.3,
      detourTime: '+ 3분',
      tags: ['길거리음식', '매콤함']
    },
    {
      id: 3,
      name: '서촌 한정식',
      location: '경복궁역 2번 출구',
      type: '전통 한식',
      rating: 4.8,
      detourTime: '+ 12분',
      tags: ['전통', '정갈함', '건강']
    }
  ];

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {/* Input Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MapPin className="w-5 h-5 text-blue-600" />
            경로 입력
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <div>
              <label className="block text-sm mb-1">출발지</label>
              <Input
                value={departure}
                onChange={(e) => setDeparture(e.target.value)}
                placeholder="출발지를 입력하세요"
              />
            </div>
            <div>
              <label className="block text-sm mb-1">도착지</label>
              <Input
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                placeholder="도착지를 입력하세요"
              />
            </div>
          </div>
          
          <div className="flex gap-2 flex-wrap">
            <Badge variant="secondary">시내버스</Badge>
            <Badge variant="outline">지하철+버스</Badge>
            <Badge variant="outline">도보 최소화</Badge>
          </div>
          
          <Button className="w-full">
            요금·소요시간 계산
          </Button>
        </CardContent>
      </Card>

      {/* Map Preview */}
      <Card>
        <CardContent className="p-4">
          <div className="bg-gray-100 rounded-lg h-32 flex items-center justify-center mb-3">
            <span className="text-gray-500">경로 미리보기 (지도)</span>
          </div>
          <div className="text-sm text-gray-600">
            {departure} → {destination}
          </div>
        </CardContent>
      </Card>

      {/* Route Results */}
      <div className="grid grid-cols-3 gap-3">
        <Card>
          <CardContent className="p-3 text-center">
            <Clock className="w-5 h-5 text-blue-600 mx-auto mb-1" />
            <div className="text-sm text-gray-600">소요시간</div>
            <div className="font-semibold">{routeResults.duration}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-3 text-center">
            <CreditCard className="w-5 h-5 text-green-600 mx-auto mb-1" />
            <div className="text-sm text-gray-600">예상 요금</div>
            <div className="font-semibold">{routeResults.fare}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-3 text-center">
            <RefreshCw className="w-5 h-5 text-orange-600 mx-auto mb-1" />
            <div className="text-sm text-gray-600">환승 횟수</div>
            <div className="font-semibold">{routeResults.transfers}</div>
          </CardContent>
        </Card>
      </div>

      {/* Side Widgets */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <h3 className="text-sm font-medium mb-2">날씨 팁</h3>
            <p className="text-sm text-gray-600">
              오늘 선선함 → 따뜻한 국물 요리 추천
            </p>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4">
            <h3 className="text-sm font-medium mb-2">사진으로 음식 인식 (베타)</h3>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-3 text-center">
              <Camera className="w-6 h-6 text-gray-400 mx-auto mb-1" />
              <span className="text-xs text-gray-500">사진 업로드</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Food Recommendations */}
      <Card>
        <CardHeader>
          <CardTitle>이동 경로 내 음식 추천</CardTitle>
          <p className="text-sm text-gray-600">
            경로상에서 들를 수 있는 맛집들을 추천해드려요
          </p>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {foodRecommendations.map((food) => (
              <div key={food.id} className="border rounded-lg p-3">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <h4 className="font-medium">{food.name}</h4>
                    <p className="text-sm text-gray-600">{food.location}</p>
                  </div>
                  <div className="flex items-center gap-1 text-sm">
                    <Star className="w-4 h-4 text-yellow-500 fill-current" />
                    <span>{food.rating}</span>
                  </div>
                </div>
                
                <div className="flex items-center justify-between">
                  <div className="flex gap-1 flex-wrap">
                    {food.tags.map((tag, idx) => (
                      <Badge key={idx} variant="outline" className="text-xs">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-blue-600">{food.detourTime}</span>
                    <Button size="sm" variant="outline">상세</Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}