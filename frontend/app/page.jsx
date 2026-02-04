import ImageUploadWidget from '../components/ImageUploadWidget';

export default function HomePage() {
  return  (
      <div className="min-h-screen bg-black text-white font-sans">
      <header className="flex justify-between items-center ps-4">
        <div className="sm:flex items-center gap-4">
          <h1 className="text-2xl font-bold"><a href='#'>LottaHelper</a></h1>
          <p className="text-sm">+7 (966) 872-12-02</p>
        </div>
        <button className="bg-gray-600 px-4 py-2 w-1/8">МЕНЮ</button>
      </header>
      
      <main className="px-4 py-8">
        <h2 className="text-xl text-center mb-8 font-medium">
          Загрузите интерьерное решение, и мы подберем для вас мебель!
        </h2>
        <ImageUploadWidget />
      </main>

      <footer className="py-8 px-8 mt-8 border-t border-gray-800">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
          <div className="space-y-3">
            <ul className="space-y-2 text-sm">
              <li><a href='#'>ДИВАНЫ</a></li>
              <li><a href='#'>КРОВАТИ</a></li>
              <li><a href='#'>ДЕТСКИЕ КРОВАТИ</a></li>
              <li><a href='#'>СТУЛЬЯ</a></li>
              <li><a href='#'>КРЕСЛА</a></li>
              <li><a href='#'>СТОЛЫ</a></li>
              <li><a href='#'>ПРИСТАВНЫЕ СТОЛЫ</a></li>
              <li><a href='#'>ЖУРНАЛЬНЫЕ СТОЛЫ</a></li>
              <li><a href='#'>СТЕЛЛАЖИ</a></li>
              <li><a href='#'>ВЕШАЛКИ, ЗЕРКАЛА, ПУФЫ</a></li>
              <li><a href='#'>УЛИЧНАЯ МЕБЕЛЬ</a></li>
              <li><a href='#'>TV-ТУМБА</a></li>
            </ul>
          </div>

          <div className="space-y-3">
            <ul className="space-y-2 text-sm">
              <li><a href='#'>ПЕРЕГОРОДКИ</a></li>
              <li><a href='#'>КУХНИ, ШКАФЫ, ГАРДЕРОБНЫЕ</a></li>
              <li><a href='#'>КОВРЫ</a></li>
              <li><a href='#'>ПАНЕЛИ ШПОНИРОВАННЫЕ</a></li>
              <li><a href='#'>ПАНЕЛИ С ТЕСНЕНИЕМ</a></li>
              <li><a href='#'>СВЕТ</a></li>
              <li><a href='#'>ПРОИЗВОДСТВО</a></li>
              <li><a href='#'>ДИЗАЙН-СТУДИЯ</a></li>
              <li><a href='#'>ОПЛАТА И ДОСТАВКА</a></li>
              <li><a href='#'>БЛОГ</a></li>
              <li><a href='#'>КОНТАКТЫ</a></li>
            </ul>
          </div>

          <div className="space-y-3">
            <div className="text-left">
              <p className="text-xl md:text-3xl font-bold mb-2">+7 (966) 872-12-02</p>
              <div className="flex justify-start space-x-4 mb-3">
                <a href='https://www.youtube.com/@ruslan_morgan'>
                  <img 
                    src="/youtube.svg" 
                    alt="Youtube" 
                    className="w-10 h-10 opacity-70 hover:opacity-100 transition-opacity"
                  />
                </a>
                <a href='https://www.instagram.com/ruslan_morgan_?igsh=MXhwOHoyb3U4eDU3eA%3D%3D&utm_source=qr'>
                  <img 
                    src="/instagram.svg" 
                    alt="Instagram" 
                    className="w-10 h-10 opacity-70 hover:opacity-100 transition-opacity"
                  />
                </a>
                <a href='https://vk.com/lottahome'>
                  <img 
                    src="/vk.svg" 
                    alt="VK" 
                    className="w-10 h-10 opacity-70 hover:opacity-100 transition-opacity"
                  />
                </a>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-sm mb-1">LOTTAHOME@YANDEX.RU</p>
              <p className="text-sm mb-1">
                <a href='whatsapp://send?phone=79668721202' className="hover:underline">НАПИСАТЬ В WHATSAPP</a>
              </p>
              <p className="text-sm">
                <a href='https://t.me/Lotta_home' className="hover:underline">НАПИСАТЬ В TELEGRAM</a>
              </p>
          </div>
        </div>
      </footer>
    </div>
  );
}