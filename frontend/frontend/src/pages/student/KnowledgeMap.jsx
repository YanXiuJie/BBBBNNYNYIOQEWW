import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
} from 'chart.js';
import { Radar } from 'react-chartjs-2';

// 注册 Chart.js 组件
ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
);

export default function KnowledgeMap() {
  const [knowledgeMap, setKnowledgeMap] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedChapter, setSelectedChapter] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchKnowledgeMap();
  }, [selectedChapter]);

  const fetchKnowledgeMap = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('token');
      const url = selectedChapter
        ? `/student/knowledge-map?chapter_id=${selectedChapter}`
        : '/student/knowledge-map';

      const response = await axios.get(url, {
        headers: { Authorization: `Bearer ${token}` }
      });

      setKnowledgeMap(response.data.knowledge_map);
      setSummary(response.data.summary);
      setError(null);
    } catch (err) {
      setError('Gagal memuatkan peta pengetahuan');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // 准备雷达图数据（只显示有尝试的前10个知识点）
  const getRadarData = () => {
    const attempted = knowledgeMap.filter(k => k.attempt_count > 0);
    const topTen = attempted.slice(0, 10);

    return {
      labels: topTen.map(k => k.subtopic_title_ms),
      datasets: [{
        label: 'Kebarangkalian Penguasaan (%)',
        data: topTen.map(k => k.mastery_probability * 100),
        backgroundColor: 'rgba(59, 130, 246, 0.2)',
        borderColor: 'rgb(59, 130, 246)',
        borderWidth: 2,
        pointBackgroundColor: 'rgb(59, 130, 246)',
        pointBorderColor: '#fff',
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: 'rgb(59, 130, 246)',
      }]
    };
  };

  const radarOptions = {
    scales: {
      r: {
        beginAtZero: true,
        max: 100,
        ticks: {
          stepSize: 20
        }
      }
    },
    plugins: {
      legend: {
        display: false
      }
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="text-lg">Memuatkan peta pengetahuan...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      </div>
    );
  }

  const attemptedCount = knowledgeMap.filter(k => k.attempt_count > 0).length;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* 页头 */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-800 mb-2">
          Peta Pengetahuan Saya
        </h1>
        <p className="text-gray-600">
          Analisis AI menunjukkan kebarangkalian penguasaan setiap subtopik berdasarkan prestasi anda.
        </p>
      </div>

      {/* 摘要统计卡片 */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="text-sm text-blue-600 font-semibold mb-1">
              Jumlah Subtopik
            </div>
            <div className="text-3xl font-bold text-blue-700">
              {summary.total_subtopics}
            </div>
          </div>

          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="text-sm text-green-600 font-semibold mb-1">
              Telah Dicuba
            </div>
            <div className="text-3xl font-bold text-green-700">
              {summary.attempted_count}
            </div>
          </div>

          <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
            <div className="text-sm text-purple-600 font-semibold mb-1">
              Dikuasai
            </div>
            <div className="text-3xl font-bold text-purple-700">
              {summary.mastered_count}
            </div>
          </div>

          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <div className="text-sm text-yellow-600 font-semibold mb-1">
              Purata Penguasaan
            </div>
            <div className="text-3xl font-bold text-yellow-700">
              {(summary.average_mastery * 100).toFixed(0)}%
            </div>
          </div>
        </div>
      )}

      {/* 雷达图 */}
      {attemptedCount > 0 && (
        <div className="bg-white rounded-lg shadow-md p-6 mb-8">
          <h2 className="text-xl font-bold text-gray-800 mb-4">
            Visualisasi Radar (10 Subtopik Pertama)
          </h2>
          <div className="max-w-2xl mx-auto">
            <Radar data={getRadarData()} options={radarOptions} />
          </div>
        </div>
      )}

      {/* 知识点详细列表 */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-xl font-bold text-gray-800 mb-4">
          Analisis Terperinci
        </h2>

        {/* 图例说明 */}
        <div className="mb-4 p-4 bg-gray-50 rounded-lg">
          <div className="text-sm font-semibold text-gray-700 mb-2">
            Status Penguasaan:
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
            <div className="flex items-center">
              <div className="w-3 h-3 bg-red-500 rounded-full mr-2"></div>
              <span>Memerlukan Bantuan (&lt;40%)</span>
            </div>
            <div className="flex items-center">
              <div className="w-3 h-3 bg-yellow-500 rounded-full mr-2"></div>
              <span>Dalam Pembangunan (40-70%)</span>
            </div>
            <div className="flex items-center">
              <div className="w-3 h-3 bg-blue-500 rounded-full mr-2"></div>
              <span>Mahir (70-90%)</span>
            </div>
            <div className="flex items-center">
              <div className="w-3 h-3 bg-green-500 rounded-full mr-2"></div>
              <span>Dikuasai (≥90%)</span>
            </div>
          </div>
        </div>

        {/* 知识点卡片 */}
        <div className="space-y-3">
          {knowledgeMap.map(item => (
            <div
              key={item.subtopic_id}
              className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex justify-between items-start mb-3">
                <div className="flex-1">
                  <h3 className="font-semibold text-gray-800 mb-1">
                    {item.subtopic_title_ms}
                  </h3>
                  <div className="flex items-center space-x-4 text-sm text-gray-600">
                    <span>{item.attempt_count} percubaan</span>
                    {item.last_attempt_correct !== null && (
                      <span className={item.last_attempt_correct ? 'text-green-600' : 'text-red-600'}>
                        Terakhir: {item.last_attempt_correct ? 'Betul ✓' : 'Salah ✗'}
                      </span>
                    )}
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-3xl font-bold text-gray-800">
                    {(item.mastery_probability * 100).toFixed(0)}%
                  </div>
                  <div className={`text-sm font-semibold ${getStatusColor(item.status)}`}>
                    {item.status_ms}
                  </div>
                </div>
              </div>

              {/* 进度条 */}
              <div className="relative w-full bg-gray-200 rounded-full h-3 mb-2">
                <div
                  className={`h-3 rounded-full transition-all ${getProgressColor(item.mastery_probability)}`}
                  style={{ width: `${item.mastery_probability * 100}%` }}
                >
                  {/* 置信度指示器 */}
                  {item.confidence < 1 && (
                    <div
                      className="absolute top-0 right-0 h-3 bg-gray-300 opacity-50 rounded-r-full"
                      style={{ width: `${(1 - item.confidence) * 100}%` }}
                    ></div>
                  )}
                </div>
              </div>

              {/* 置信度和建议 */}
              <div className="flex justify-between items-center text-xs text-gray-600">
                <span>
                  Keyakinan: {(item.confidence * 100).toFixed(0)}%
                </span>
                {item.confidence < 0.5 && (
                  <span className="text-orange-600 font-semibold">
                    ⚠️ Data terhad - perlukan lebih latihan
                  </span>
                )}
                {item.mastery_probability < 0.4 && item.confidence >= 0.5 && (
                  <button
                    onClick={() => navigate(`/student/adaptive-practice?subtopic_id=${item.subtopic_id}`)}
                    className="text-blue-600 hover:text-blue-800 font-semibold"
                  >
                    Mulakan Latihan →
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 说明文字 */}
      <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <h3 className="font-semibold text-blue-800 mb-2">
          📊 Tentang Peta Pengetahuan
        </h3>
        <p className="text-sm text-blue-700">
          Sistem ini menggunakan algoritma <strong>Knowledge Tracing</strong> yang menganalisis
          sejarah jawapan anda untuk menganggarkan kebarangkalian penguasaan setiap subtopik.
          Berbeza dengan kiraan mudah "betul/salah", algoritma ini mengambil kira:
        </p>
        <ul className="list-disc list-inside text-sm text-blue-700 mt-2 space-y-1">
          <li>Kesukaran soalan yang dijawab</li>
          <li>Urutan masa jawapan (prestasi terkini lebih penting)</li>
          <li>Kebarangkalian "meneka betul" vs "benar-benar faham"</li>
          <li>Kebarangkalian "kesilapan cuai" untuk topik yang sudah dikuasai</li>
        </ul>
      </div>
    </div>
  );
}

function getStatusColor(status) {
  const colors = {
    struggling: 'text-red-600',
    developing: 'text-yellow-600',
    proficient: 'text-blue-600',
    mastered: 'text-green-600'
  };
  return colors[status] || 'text-gray-600';
}

function getProgressColor(probability) {
  if (probability < 0.4) return 'bg-red-500';
  if (probability < 0.7) return 'bg-yellow-500';
  if (probability < 0.9) return 'bg-blue-500';
  return 'bg-green-500';
}
