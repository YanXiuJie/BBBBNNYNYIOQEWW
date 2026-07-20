import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

export default function StudentKnowledgeAnalysis() {
  const { studentId } = useParams();
  const navigate = useNavigate();
  const [student, setStudent] = useState(null);
  const [subtopics, setSubtopics] = useState([]);
  const [selectedSubtopic, setSelectedSubtopic] = useState(null);
  const [selectedDifficulty, setSelectedDifficulty] = useState('medium');
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSubtopics();
  }, []);

  useEffect(() => {
    if (selectedSubtopic) {
      fetchPrediction();
    }
  }, [selectedSubtopic, selectedDifficulty]);

  const fetchSubtopics = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get('/syllabus', {
        headers: { Authorization: `Bearer ${token}` }
      });

      // 展平所有 subtopics
      const allSubtopics = response.data.chapters.flatMap(ch =>
        ch.subtopics.map(st => ({ ...st, chapter_title: ch.title_ms }))
      );

      setSubtopics(allSubtopics);
      if (allSubtopics.length > 0) {
        setSelectedSubtopic(allSubtopics[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch subtopics', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchPrediction = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(
        `/teacher/students/${studentId}/knowledge-prediction?subtopic_id=${selectedSubtopic}&difficulty=${selectedDifficulty}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setPrediction(response.data);
      setStudent(response.data.student);
    } catch (err) {
      console.error('Failed to fetch prediction', err);
    }
  };

  if (loading) {
    return <div className="p-6">Memuatkan...</div>;
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* 页头 */}
      <div className="mb-6">
        <button
          onClick={() => navigate(-1)}
          className="text-blue-600 hover:text-blue-800 mb-2"
        >
          ← Kembali
        </button>
        <h1 className="text-3xl font-bold text-gray-800">
          Analisis Pengetahuan Murid
        </h1>
        {student && (
          <p className="text-gray-600 mt-1">
            Murid: <strong>{student.full_name}</strong> (@{student.username})
          </p>
        )}
      </div>

      {/* 选择器 */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">
          Pilih Subtopik dan Kesukaran
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Subtopic 选择 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Subtopik
            </label>
            <select
              value={selectedSubtopic || ''}
              onChange={(e) => setSelectedSubtopic(parseInt(e.target.value))}
              className="w-full border border-gray-300 rounded-lg px-3 py-2"
            >
              {subtopics.map(st => (
                <option key={st.id} value={st.id}>
                  {st.chapter_title} - {st.title_ms}
                </option>
              ))}
            </select>
          </div>

          {/* Difficulty 选择 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Kesukaran Soalan
            </label>
            <select
              value={selectedDifficulty}
              onChange={(e) => setSelectedDifficulty(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2"
            >
              <option value="easy">Mudah</option>
              <option value="medium">Sederhana</option>
              <option value="hard">Sukar</option>
            </select>
          </div>
        </div>
      </div>

      {/* 预测结果 */}
      {prediction && (
        <>
          {/* 当前状态 */}
          <div className="bg-white rounded-lg shadow-md p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">
              Status Semasa
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="border border-gray-200 rounded-lg p-4">
                <div className="text-sm text-gray-600 mb-1">
                  Kebarangkalian Penguasaan
                </div>
                <div className="text-3xl font-bold text-blue-600">
                  {(prediction.current_state.mastery_probability * 100).toFixed(1)}%
                </div>
              </div>

              <div className="border border-gray-200 rounded-lg p-4">
                <div className="text-sm text-gray-600 mb-1">
                  Keyakinan Anggaran
                </div>
                <div className="text-3xl font-bold text-purple-600">
                  {(prediction.current_state.confidence * 100).toFixed(0)}%
                </div>
              </div>

              <div className="border border-gray-200 rounded-lg p-4">
                <div className="text-sm text-gray-600 mb-1">
                  Jumlah Percubaan
                </div>
                <div className="text-3xl font-bold text-gray-700">
                  {prediction.current_state.attempt_count}
                </div>
              </div>
            </div>
          </div>

          {/* 预测概率（不同难度） */}
          <div className="bg-white rounded-lg shadow-md p-6 mb-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">
              Ramalan Prestasi (Kebarangkalian Jawab Betul)
            </h2>

            <div className="space-y-3">
              {['easy', 'medium', 'hard'].map(diff => {
                const prob = prediction.predictions[diff];
                const isSelected = diff === selectedDifficulty;

                return (
                  <div key={diff} className={`border rounded-lg p-4 ${isSelected ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}`}>
                    <div className="flex justify-between items-center mb-2">
                      <div>
                        <span className="font-semibold text-gray-800">
                          {diff === 'easy' ? 'Mudah' : diff === 'medium' ? 'Sederhana' : 'Sukar'}
                        </span>
                        {isSelected && (
                          <span className="ml-2 text-xs text-blue-600 font-semibold">
                            ← Dipilih
                          </span>
                        )}
                      </div>
                      <div className="text-2xl font-bold">
                        {(prob * 100).toFixed(1)}%
                      </div>
                    </div>

                    {/* 进度条 */}
                    <div className="w-full bg-gray-200 rounded-full h-3">
                      <div
                        className={`h-3 rounded-full ${getPredictionColor(prob)}`}
                        style={{ width: `${prob * 100}%` }}
                      ></div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 建议 */}
          <div className={`rounded-lg shadow-md p-6 ${getRecommendationStyle(prediction.predictions[selectedDifficulty])}`}>
            <h2 className="text-lg font-semibold mb-2">
              💡 Cadangan
            </h2>
            <p className="text-lg font-medium mb-2">
              {prediction.recommendation_ms}
            </p>
            <p className="text-sm opacity-90">
              Berdasarkan kebarangkalian jawab betul {(prediction.predictions[selectedDifficulty] * 100).toFixed(1)}%
              untuk soalan kesukaran <strong>{selectedDifficulty === 'easy' ? 'mudah' : selectedDifficulty === 'medium' ? 'sederhana' : 'sukar'}</strong>.
            </p>
          </div>

          {/* 说明 */}
          <div className="mt-6 p-4 bg-gray-50 border border-gray-200 rounded-lg">
            <h3 className="font-semibold text-gray-800 mb-2">
              ℹ️ Cara Menggunakan Ramalan Ini
            </h3>
            <ul className="text-sm text-gray-700 space-y-1 list-disc list-inside">
              <li>
                <strong>Kebarangkalian &gt; 80%:</strong> Murid bersedia untuk kesukaran lebih tinggi
              </li>
              <li>
                <strong>Kebarangkalian 40-80%:</strong> Kesukaran semasa sesuai
              </li>
              <li>
                <strong>Kebarangkalian &lt; 40%:</strong> Pertimbangkan kesukaran lebih rendah atau bimbingan tambahan
              </li>
              <li>
                Keyakinan rendah bermakna data terhad - ramalan mungkin kurang tepat
              </li>
            </ul>
          </div>
        </>
      )}
    </div>
  );
}

function getPredictionColor(probability) {
  if (probability < 0.4) return 'bg-red-500';
  if (probability < 0.7) return 'bg-yellow-500';
  if (probability < 0.85) return 'bg-blue-500';
  return 'bg-green-500';
}

function getRecommendationStyle(probability) {
  if (probability < 0.4) return 'bg-red-50 border border-red-200 text-red-800';
  if (probability < 0.7) return 'bg-yellow-50 border border-yellow-200 text-yellow-800';
  if (probability < 0.85) return 'bg-blue-50 border border-blue-200 text-blue-800';
  return 'bg-green-50 border border-green-200 text-green-800';
}
