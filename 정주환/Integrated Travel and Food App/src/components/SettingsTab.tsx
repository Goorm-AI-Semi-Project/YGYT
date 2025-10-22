import { useState } from 'react';
import { Bus, Train, Accessibility, Globe, Bell, User, Shield, Info } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Switch } from './ui/switch';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Separator } from './ui/separator';

export function SettingsTab() {
  const [transportMode, setTransportMode] = useState('mixed'); // 'bus' or 'mixed'
  const [lowActivityMode, setLowActivityMode] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState('ko');
  const [notifications, setNotifications] = useState(true);

  const languages = [
    { code: 'ko', name: '한국어', flag: '🇰🇷' },
    { code: 'en', name: 'English', flag: '🇺🇸' },
    { code: 'ja', name: '日本語', flag: '🇯🇵' },
    { code: 'zh', name: '中文', flag: '🇨🇳' },
    { code: 'es', name: 'Español', flag: '🇪🇸' }
  ];

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {/* User Profile */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="w-5 h-5 text-blue-600" />
            프로필
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-gray-200 rounded-full flex items-center justify-center">
              <User className="w-6 h-6 text-gray-500" />
            </div>
            <div>
              <p className="font-medium">사용자</p>
              <p className="text-sm text-gray-600">서울 거주 3년차</p>
            </div>
          </div>
          <Button variant="outline" className="w-full">
            프로필 편집
          </Button>
        </CardContent>
      </Card>

      {/* Transport Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bus className="w-5 h-5 text-green-600" />
            교통 모드
          </CardTitle>
          <p className="text-sm text-gray-600">
            선호하는 교통수단을 설정하세요
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Bus className="w-5 h-5 text-blue-600" />
                <div>
                  <p className="font-medium">시내버스 전용</p>
                  <p className="text-sm text-gray-600">버스만 이용한 경로</p>
                </div>
              </div>
              <Switch
                checked={transportMode === 'bus'}
                onCheckedChange={() => setTransportMode(transportMode === 'bus' ? 'mixed' : 'bus')}
              />
            </div>
            
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Train className="w-5 h-5 text-purple-600" />
                <div>
                  <p className="font-medium">지하철 + 버스</p>
                  <p className="text-sm text-gray-600">최적 경로 조합</p>
                </div>
              </div>
              <Switch
                checked={transportMode === 'mixed'}
                onCheckedChange={() => setTransportMode(transportMode === 'mixed' ? 'bus' : 'mixed')}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Accessibility Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Accessibility className="w-5 h-5 text-orange-600" />
            접근성 설정
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">저활동량 모드</p>
              <p className="text-sm text-gray-600">걷기 최소화, 엘리베이터 우선, 휴식 알림</p>
            </div>
            <Switch
              checked={lowActivityMode}
              onCheckedChange={setLowActivityMode}
            />
          </div>
          
          {lowActivityMode && (
            <div className="bg-orange-50 p-3 rounded-lg">
              <p className="text-sm text-orange-800">
                ✓ 도보 거리 200m 이하 우선<br />
                ✓ 엘리베이터/에스컬레이터 경로<br />
                ✓ 30분마다 휴식 알림
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Language Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Globe className="w-5 h-5 text-indigo-600" />
            언어 설정
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-2">
            {languages.map((lang) => (
              <Button
                key={lang.code}
                variant={selectedLanguage === lang.code ? "default" : "outline"}
                onClick={() => setSelectedLanguage(lang.code)}
                className="flex items-center gap-2 h-auto p-3"
              >
                <span className="text-lg">{lang.flag}</span>
                <span className="text-sm">{lang.name}</span>
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Notification Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="w-5 h-5 text-yellow-600" />
            알림 설정
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">푸시 알림</p>
              <p className="text-sm text-gray-600">경로 업데이트, 음식 추천 등</p>
            </div>
            <Switch
              checked={notifications}
              onCheckedChange={setNotifications}
            />
          </div>
          
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">위치 기반 추천</p>
              <p className="text-sm text-gray-600">현재 위치 주변 맛집 알림</p>
            </div>
            <Switch defaultChecked />
          </div>
        </CardContent>
      </Card>

      {/* Data & Privacy */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-red-600" />
            데이터 및 개인정보
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button variant="outline" className="w-full justify-start">
            개인정보 처리방침
          </Button>
          <Button variant="outline" className="w-full justify-start">
            데이터 내보내기
          </Button>
          <Button variant="outline" className="w-full justify-start text-red-600">
            계정 삭제
          </Button>
        </CardContent>
      </Card>

      {/* App Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Info className="w-5 h-5 text-gray-600" />
            앱 정보
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex justify-between">
            <span className="text-sm">버전</span>
            <span className="text-sm text-gray-600">1.0.0</span>
          </div>
          <div className="flex justify-between">
            <span className="text-sm">마지막 업데이트</span>
            <span className="text-sm text-gray-600">2025.01.15</span>
          </div>
          <Separator />
          <Button variant="outline" className="w-full justify-start">
            도움말 및 지원
          </Button>
          <Button variant="outline" className="w-full justify-start">
            피드백 보내기
          </Button>
        </CardContent>
      </Card>

      {/* Bottom Spacing */}
      <div className="h-4"></div>
    </div>
  );
}