import { useState } from 'react';
import { Search, Filter, MapPin, Star, Clock } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { Slider } from './ui/slider';
import { Switch } from './ui/switch';

export function FoodExplorationTab() {
  const [searchQuery, setSearchQuery] = useState('');
  const [isHot, setIsHot] = useState(true);
  const [spiceLevel, setSpiceLevel] = useState([2]);
  const [adventureLevel, setAdventureLevel] = useState([3]);

  const foodItems = [
    {
      id: 1,
      name: '북촌 전통 찹쌀떡',
      region: '종로구 북촌',
      story: '조선시대부터 전해내려온 궁중 떡 제조법',
      tags: ['달콤함', '전통', '찹쌀'],
      rating: 4.7,
      routePosition: '경복궁역 5분 거리',
      temperature: 'hot',
      spice: 0,
      adventure: 2
    },
    {
      id: 2,
      name: '이태원 퓨전 타코',
      region: '용산구 이태원',
      story: '1970년대 미군부대 문화와 한국 음식의 만남',
      tags: ['매콤함', '퓨전', '멕시칸'],
      rating: 4.4,
      routePosition: '이태원역 3번 출구',
      temperature: 'hot',
      spice: 3,
      adventure: 4
    },
    {
      id: 3,
      name: '명동 냉면',
      region: '중구 명동',
      story: '평양 실향민이 1950년대 정착하며 시작된 맛',
      tags: ['시원함', '메밀', '전통'],
      rating: 4.8,
      routePosition: '명동역 2분 거리',
      temperature: 'cold',
      spice: 1,
      adventure: 1
    },
    {
      id: 4,
      name: '홍대 크래프트 맥주',
      region: '마포구 홍대',
      story: '2000년대 청년 문화와 함께 성장한 수제맥주 거리',
      tags: ['시원함', '홉', '수제'],
      rating: 4.5,
      routePosition: '홍대입구역 도보 8분',
      temperature: 'cold',
      spice: 0,
      adventure: 3
    }
  ];

  const filteredItems = foodItems.filter(item => {
    const matchesSearch = searchQuery === '' || 
      item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.tags.some(tag => tag.includes(searchQuery));
    
    const matchesTemperature = (isHot && item.temperature === 'hot') || 
      (!isHot && item.temperature === 'cold');
    
    const matchesSpice = item.spice <= spiceLevel[0];
    const matchesAdventure = Math.abs(item.adventure - adventureLevel[0]) <= 1;
    
    return matchesSearch && matchesTemperature && matchesSpice && matchesAdventure;
  });

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {/* Search and Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="w-5 h-5 text-blue-600" />
            음식 탐색
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="음식명, 재료로 검색..."
              className="pl-10"
            />
          </div>
          
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm">온도</span>
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500">찬</span>
                <Switch checked={isHot} onCheckedChange={setIsHot} />
                <span className="text-sm text-gray-500">온</span>
              </div>
            </div>
            
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm">맵기 수준</span>
                <span className="text-sm text-gray-500">{spiceLevel[0]}/5</span>
              </div>
              <Slider
                value={spiceLevel}
                onValueChange={setSpiceLevel}
                max={5}
                step={1}
                className="w-full"
              />
            </div>
            
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm">모험 지수 (도전성)</span>
                <span className="text-sm text-gray-500">{adventureLevel[0]}/5</span>
              </div>
              <Slider
                value={adventureLevel}
                onValueChange={setAdventureLevel}
                max={5}
                step={1}
                className="w-full"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Story Filter */}
      <Card>
        <CardHeader>
          <CardTitle>스토리 필터</CardTitle>
          <p className="text-sm text-gray-600">
            지역 역사나 문화적 배경으로 검색해보세요
          </p>
        </CardHeader>
        <CardContent>
          <Input
            placeholder="예: 조선시대, 일제강점기, 미군부대, 6.25전쟁..."
            className="mb-3"
          />
          <div className="flex gap-2 flex-wrap">
            <Badge variant="secondary">조선왕조</Badge>
            <Badge variant="secondary">일제강점기</Badge>
            <Badge variant="secondary">6.25전쟁</Badge>
            <Badge variant="secondary">실향민</Badge>
            <Badge variant="secondary">청년문화</Badge>
          </div>
        </CardContent>
      </Card>

      {/* Food Results */}
      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <h3 className="font-medium">검색 결과 ({filteredItems.length}개)</h3>
          <Button variant="outline" size="sm">
            <Filter className="w-4 h-4 mr-1" />
            정렬
          </Button>
        </div>
        
        {filteredItems.map((food) => (
          <Card key={food.id}>
            <CardContent className="p-4">
              <div className="flex justify-between items-start mb-3">
                <div>
                  <h4 className="font-medium mb-1">{food.name}</h4>
                  <div className="flex items-center gap-1 text-sm text-gray-600 mb-1">
                    <MapPin className="w-3 h-3" />
                    <span>{food.region}</span>
                  </div>
                  <div className="flex items-center gap-1 text-sm">
                    <Star className="w-4 h-4 text-yellow-500 fill-current" />
                    <span>{food.rating}</span>
                  </div>
                </div>
                <Badge variant="outline">{food.routePosition}</Badge>
              </div>
              
              <p className="text-sm text-gray-600 mb-3 leading-relaxed">
                {food.story}
              </p>
              
              <div className="flex items-center justify-between">
                <div className="flex gap-1 flex-wrap">
                  {food.tags.map((tag, idx) => (
                    <Badge key={idx} variant="secondary" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                </div>
                <Button size="sm">상세 보기</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      
      {filteredItems.length === 0 && (
        <Card>
          <CardContent className="p-8 text-center">
            <p className="text-gray-500">검색 조건에 맞는 음식이 없습니다.</p>
            <p className="text-sm text-gray-400 mt-1">필터를 조정해보세요.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}