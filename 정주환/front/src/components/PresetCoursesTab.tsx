import { useState } from 'react';
import { Clock, DollarSign, MapPin, Plus, Tag, Bookmark } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';

export function PresetCoursesTab() {
  const [selectedCourse, setSelectedCourse] = useState(null);

  const presetCourses = [
    {
      id: 1,
      title: '한옥마을 + 따뜻한 국물 코스',
      duration: '3시간 30분',
      walkingDistance: '2.1km',
      budget: '25,000원',
      theme: ['전통', '역사', '따뜻함'],
      description: '북촌한옥마을을 거닐며 조선시대 정취를 느끼고, 전통 칼국수로 마무리',
      stops: [
        { name: '경복궁', time: '60분', type: '관광' },
        { name: '북촌한옥마을', time: '90분', type: '관광' },
        { name: '삼청동 전통찻집', time: '30분', type: '휴식' },
        { name: '인사동 칼국수 맛집', time: '50분', type: '식사' }
      ],
      weather: ['맑음', '흐림'],
      season: '가을'
    },
    {
      id: 2,
      title: 'K-드라마 성지 + 길거리 간식',
      duration: '4시간',
      walkingDistance: '3.2km',
      budget: '18,000원',
      theme: ['한류', '젊음', '간식'],
      description: '드라마 촬영지를 돌며 한류 문화를 체험하고 핫한 간식 맛보기',
      stops: [
        { name: '남산타워', time: '90분', type: '관광' },
        { name: '명동 쇼핑', time: '60분', type: '쇼핑' },
        { name: '홍대 걷기', time: '45분', type: '관광' },
        { name: '망원시장 길거리음식', time: '45분', type: '식사' }
      ],
      weather: ['맑음'],
      season: '봄'
    },
    {
      id: 3,
      title: '비 오는 날 실내 박물관 + 닭한마리',
      duration: '3시간',
      walkingDistance: '0.8km',
      budget: '22,000원',
      theme: ['실내', '문화', '따뜻함'],
      description: '날씨가 좋지 않을 때 실내에서 문화생활과 따뜻한 한 끼',
      stops: [
        { name: '국립중앙박물관', time: '120분', type: '문화' },
        { name: '용산 아이파크몰', time: '30분', type: '쇼핑' },
        { name: '동대문 닭한마리 골목', time: '50분', type: '식사' }
      ],
      weather: ['비', '눈'],
      season: '겨울'
    },
    {
      id: 4,
      title: '한강 피크닉 + 치킨&맥주',
      duration: '4시간 30분',
      walkingDistance: '1.5km',
      budget: '30,000원',
      theme: ['자연', '여유', '시원함'],
      description: '한강에서 여유로운 피크닉과 치맥으로 힐링하는 코스',
      stops: [
        { name: '반포한강공원', time: '150분', type: '휴식' },
        { name: '세빛섬', time: '60분', type: '관광' },
        { name: '한강 치킨 배달', time: '60분', type: '식사' }
      ],
      weather: ['맑음'],
      season: '여름'
    }
  ];

  const themes = ['식도락', '역사', '레저', '문화', '자연', '쇼핑', '한류'];

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {/* Header */}
      <Card>
        <CardHeader>
          <CardTitle>프리셋 코스</CardTitle>
          <p className="text-sm text-gray-600">
            날씨와 시간에 맞춰 준비된 추천 코스를 선택하세요
          </p>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2 flex-wrap mb-4">
            {themes.map((theme) => (
              <Badge key={theme} variant="outline" className="cursor-pointer hover:bg-primary hover:text-white">
                {theme}
              </Badge>
            ))}
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Button variant="outline" className="flex items-center gap-2">
              <Plus className="w-4 h-4" />
              경유지 추가
            </Button>
            <Button variant="outline" className="flex items-center gap-2">
              <Tag className="w-4 h-4" />
              테마 태깅
            </Button>
            <Button variant="outline" className="flex items-center gap-2">
              <Bookmark className="w-4 h-4" />
              코스 저장
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Course List */}
      <div className="space-y-4">
        {presetCourses.map((course) => (
          <Card key={course.id} className="overflow-hidden">
            <CardHeader className="pb-3">
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle className="text-lg mb-2">{course.title}</CardTitle>
                  <p className="text-sm text-gray-600 leading-relaxed">
                    {course.description}
                  </p>
                </div>
                <Badge variant="secondary">{course.season}</Badge>
              </div>
            </CardHeader>
            
            <CardContent className="space-y-4">
              {/* Course Stats */}
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="flex flex-col items-center">
                  <Clock className="w-5 h-5 text-blue-600 mb-1" />
                  <span className="text-sm text-gray-600">소요시간</span>
                  <span className="font-medium">{course.duration}</span>
                </div>
                <div className="flex flex-col items-center">
                  <MapPin className="w-5 h-5 text-green-600 mb-1" />
                  <span className="text-sm text-gray-600">걷기거리</span>
                  <span className="font-medium">{course.walkingDistance}</span>
                </div>
                <div className="flex flex-col items-center">
                  <DollarSign className="w-5 h-5 text-yellow-600 mb-1" />
                  <span className="text-sm text-gray-600">예상예산</span>
                  <span className="font-medium">{course.budget}</span>
                </div>
              </div>

              {/* Theme Tags */}
              <div className="flex gap-1 flex-wrap">
                {course.theme.map((tag, idx) => (
                  <Badge key={idx} variant="secondary" className="text-xs">
                    {tag}
                  </Badge>
                ))}
              </div>

              {/* Course Stops */}
              {selectedCourse === course.id && (
                <div className="border-t pt-4">
                  <h4 className="font-medium mb-3">코스 일정</h4>
                  <div className="space-y-2">
                    {course.stops.map((stop, idx) => (
                      <div key={idx} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                        <div>
                          <span className="font-medium text-sm">{stop.name}</span>
                          <Badge variant="outline" className="ml-2 text-xs">
                            {stop.type}
                          </Badge>
                        </div>
                        <span className="text-sm text-gray-600">{stop.time}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Weather Info */}
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-gray-600">추천 날씨:</span>
                  {course.weather.map((w, idx) => (
                    <Badge key={idx} variant="outline" className="text-xs">
                      {w}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => setSelectedCourse(
                    selectedCourse === course.id ? null : course.id
                  )}
                  className="flex-1"
                >
                  {selectedCourse === course.id ? '접기' : '상세보기'}
                </Button>
                <Button className="flex-1">
                  코스 시작
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Custom Course Creator */}
      <Card>
        <CardHeader>
          <CardTitle>나만의 코스 만들기</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input placeholder="코스 이름을 입력하세요" />
          <div className="grid grid-cols-2 gap-3">
            <Input placeholder="예상 시간" />
            <Input placeholder="예산" />
          </div>
          <Button className="w-full">
            <Plus className="w-4 h-4 mr-2" />
            새 코스 만들기
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}