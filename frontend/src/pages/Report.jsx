import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import { investigations } from '../services/api';
import AdvancedTimelineGraph from '../components/AdvancedTimelineGraph';

function Report() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [investigation, setInvestigation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('story');
  const [expandedTimelineItem, setExpandedTimelineItem] = useState(null);

  useEffect(() => {
    const fetchInvestigation = async () => {
      try {
        const response = await investigations.get(id);
        setInvestigation(response.data);
        setLoading(false);
      } catch (error) {
        console.error('Failed to fetch investigation:', error);
        setLoading(false);
      }
    };
    fetchInvestigation();
  }, [id]);

  // Extract report data
  const reportData = investigation?.findings?.report_data || {};
  const scoutData = investigation?.findings?.scout_data || {};
  const analysis = investigation?.findings?.analysis || {};
  const executiveSummary = reportData.executive_summary || {};
  const timeline = reportData.timeline || [];
  const citations = reportData.citations || [];

  // v2 analyst fields
  const cuiResult = analysis.cui_scores || {};
  const cuiScore = cuiResult.cui_score || 0;
  const cuiLabel = cuiResult.understanding_label || 'N/A';
  const cuiComponents = cuiResult.components || {};
  const ocsScore = analysis.ocs_score || 0;
  const ocsLabel = analysis.ocs_label || 'N/A';
  const businessRisk = analysis.business_risk || {};
  const riskItems = businessRisk.risk_items || [];
  const keyFindings = analysis.key_findings || [];
  const reasoning = analysis.reasoning || [];
  const learningPath = reportData.learning_path || analysis.onboarding_graph?.learning_tiers || {};
  const safePR = reportData.safe_first_pr || {};
  const busFactor = scoutData.bus_factor_map || {};
  const narrative = investigation?.report || '';

  // Format date
  const formatDate = (dateStr) => {
    if (!dateStr) return 'Unknown';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  };

  // Get timeline event icon and color
  const getTimelineStyle = (type) => ({
    birth: { icon: '🌱', color: 'bg-green-500', borderColor: 'border-green-500' },
    peak: { icon: '🚀', color: 'bg-blue-500', borderColor: 'border-blue-500' },
    decline: { icon: '📉', color: 'bg-orange-500', borderColor: 'border-orange-500' },
    present: { icon: '🔬', color: 'bg-purple-500', borderColor: 'border-purple-500' },
  }[type] || { icon: '📌', color: 'bg-gray-500', borderColor: 'border-gray-500' });

  // Handle PDF export
  const handleExportPDF = () => {
    window.print();
  };

  // Handle share
  const handleShare = async () => {
    const shareUrl = window.location.href;
    if (navigator.share) {
      await navigator.share({
        title: `Neural Archaeologist Report: ${executiveSummary.repo_name}`,
        url: shareUrl,
      });
    } else {
      navigator.clipboard.writeText(shareUrl);
      alert('Link copied to clipboard!');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
          className="text-6xl"
        >
          📜
        </motion.div>
      </div>
    );
  }

  if (!investigation) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-4">🔍</div>
          <h2 className="text-2xl text-white mb-4">Investigation Not Found</h2>
          <Link to="/history" className="text-purple-400 hover:text-purple-300">
            ← Back to History
          </Link>
        </div>
      </div>
    );
  }

  if (investigation.status !== 'completed') {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="text-center">
          <motion.div
            animate={{ scale: [1, 1.1, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="text-6xl mb-4"
          >
            ⛏️
          </motion.div>
          <h2 className="text-2xl text-white mb-4">Investigation In Progress</h2>
          <p className="text-gray-400 mb-6">The report will be available once the excavation is complete.</p>
          <Link
            to={`/dashboard/${id}`}
            className="bg-purple-600 hover:bg-purple-500 text-white px-6 py-3 rounded-lg"
          >
            View Live Dashboard →
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 print:bg-white">
      {/* Background effects */}
      <div className="fixed inset-0 pointer-events-none print:hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-slate-950 via-purple-950/30 to-slate-950" />
        <motion.div
          className="absolute top-0 right-0 w-[600px] h-[600px] bg-purple-600/10 rounded-full blur-3xl"
          animate={{ x: [0, 30, 0], y: [0, 20, 0] }}
          transition={{ duration: 15, repeat: Infinity }}
        />
      </div>

      {/* Header */}
      <header className="relative z-10 bg-black/40 backdrop-blur-xl border-b border-white/5 sticky top-0 print:static print:bg-white print:border-gray-200">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/history')}
                className="text-gray-400 hover:text-white transition print:hidden"
              >
                ← Back
              </button>
              <div>
                <h1 className="text-xl font-bold text-white print:text-black flex items-center gap-2">
                  <span>📜</span>
                  Archaeological Report
                </h1>
                <p className="text-sm text-gray-400 print:text-gray-600 font-mono">
                  {investigation.repo_url}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 print:hidden">
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={handleShare}
                className="px-4 py-2 bg-white/5 hover:bg-white/10 text-white rounded-lg border border-white/10"
              >
                🔗 Share
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={handleExportPDF}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg"
              >
                📄 Export PDF
              </motion.button>
            </div>
          </div>
        </div>
      </header>

      <main className="relative z-10 max-w-6xl mx-auto px-4 py-8">
        {/* Executive Summary Card */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="bg-gradient-to-r from-purple-900/50 to-pink-900/50 rounded-2xl border border-white/10 p-6 print:bg-gray-100 print:border-gray-300">
            <h2 className="text-lg font-semibold text-white print:text-black mb-4 flex items-center gap-2">
              <span>📊</span>
              Executive Summary
            </h2>

            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
              <div className="bg-black/30 rounded-xl p-4 print:bg-white print:border print:border-gray-200">
                <div className="text-3xl font-bold text-white print:text-purple-600">
                  {scoutData.total_commits?.toLocaleString() || 0}
                </div>
                <div className="text-sm text-gray-400 print:text-gray-600">Total Commits</div>
              </div>
              <div className="bg-black/30 rounded-xl p-4 print:bg-white print:border print:border-gray-200">
                <div className="text-3xl font-bold text-white print:text-purple-600">
                  {scoutData.contributors_count || 0}
                </div>
                <div className="text-sm text-gray-400 print:text-gray-600">Contributors</div>
              </div>
              <div className="bg-black/30 rounded-xl p-4 print:bg-white print:border print:border-gray-200">
                <div className="text-3xl font-bold text-white print:text-purple-600">
                  {scoutData.active_period_months?.toFixed(0) || 0}
                </div>
                <div className="text-sm text-gray-400 print:text-gray-600">Active Months</div>
              </div>
              <div className="bg-black/30 rounded-xl p-4 print:bg-white print:border print:border-gray-200">
                <div className={`text-3xl font-bold ${investigation.confidence >= 80 ? 'text-green-400' :
                  investigation.confidence >= 60 ? 'text-yellow-400' : 'text-red-400'
                  } print:text-purple-600`}>
                  {investigation.confidence}%
                </div>
                <div className="text-sm text-gray-400 print:text-gray-600">Confidence</div>
              </div>
              <div className="bg-black/30 rounded-xl p-4 print:bg-white print:border print:border-gray-200">
                <div className={`text-3xl font-bold ${cuiScore >= 70 ? 'text-green-400' : cuiScore >= 40 ? 'text-yellow-400' : 'text-red-400'} print:text-purple-600`}>
                  {cuiScore.toFixed(0)}
                </div>
                <div className="text-sm text-gray-400 print:text-gray-600">CUI Score</div>
                <div className="text-xs text-gray-500 mt-1 truncate">{cuiLabel}</div>
              </div>
              <div className="bg-black/30 rounded-xl p-4 print:bg-white print:border print:border-gray-200">
                <div className={`text-3xl font-bold ${ocsScore <= 25 ? 'text-green-400' : ocsScore <= 50 ? 'text-yellow-400' : 'text-red-400'} print:text-purple-600`}>
                  {ocsScore}
                </div>
                <div className="text-sm text-gray-400 print:text-gray-600">OCS</div>
                <div className="text-xs text-gray-500 mt-1 truncate">{ocsLabel}</div>
              </div>
            </div>

            {/* Technical health + salvageability badges */}
            {(analysis.technical_health || analysis.salvageability || analysis.onboarding_difficulty) && (
              <div className="flex flex-wrap gap-3 mb-4">
                {analysis.technical_health && (
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                    analysis.technical_health === 'excellent' ? 'bg-green-500/20 text-green-300' :
                    analysis.technical_health === 'good' ? 'bg-blue-500/20 text-blue-300' :
                    analysis.technical_health === 'fair' ? 'bg-yellow-500/20 text-yellow-300' :
                    'bg-red-500/20 text-red-300'
                  }`}>
                    🏥 Health: {analysis.technical_health}
                  </span>
                )}
                {analysis.salvageability && (
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                    analysis.salvageability === 'high' ? 'bg-green-500/20 text-green-300' :
                    analysis.salvageability === 'medium' ? 'bg-yellow-500/20 text-yellow-300' :
                    analysis.salvageability === 'low' ? 'bg-orange-500/20 text-orange-300' :
                    'bg-red-500/20 text-red-300'
                  }`}>
                    🔧 Salvageability: {analysis.salvageability}
                  </span>
                )}
                {analysis.onboarding_difficulty && (
                  <span className="px-3 py-1 rounded-full text-sm font-medium bg-purple-500/20 text-purple-300">
                    🎓 Onboarding: {analysis.onboarding_difficulty}
                  </span>
                )}
              </div>
            )}

            <div className="bg-black/20 rounded-xl p-4 print:bg-white print:border print:border-gray-200">
              <h3 className="text-sm font-medium text-purple-300 print:text-purple-600 mb-2">Hypothesis</h3>
              <p className="text-white print:text-black">{analysis.hypothesis || 'No hypothesis generated'}</p>
            </div>
          </div>
        </motion.section>

        {/* Tab Navigation */}
        <div className="flex gap-2 mb-6 print:hidden overflow-x-auto pb-2">
          {[
            { id: 'story', label: '📖 Story', icon: '📖' },
            { id: 'timeline', label: '⏰ Timeline', icon: '⏰' },
            { id: 'analysis', label: '🧠 Analysis', icon: '🧠' },
            { id: 'onboarding', label: '🗺️ Onboarding', icon: '🗺️' },
            { id: 'contributors', label: '👥 Contributors', icon: '👥' },
            { id: 'github', label: '🐙 GitHub Insights', icon: '🐙' },
            { id: 'sources', label: '📚 Sources', icon: '📚' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded-lg font-medium transition whitespace-nowrap ${activeTab === tab.id
                ? 'bg-purple-600 text-white'
                : 'bg-white/5 text-gray-400 hover:bg-white/10 hover:text-white'
                }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <AnimatePresence mode="wait">
          {/* Story Tab */}
          {activeTab === 'story' && (
            <motion.section
              key="story"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/5 p-6 md:p-8 print:bg-white print:border-gray-200"
            >
              <div className="prose prose-invert max-w-none print:prose">
                <ReactMarkdown
                  components={{
                    h1: ({ children }) => (
                      <h1 className="text-3xl font-bold text-white print:text-black mb-6 border-b border-white/10 print:border-gray-300 pb-4">
                        {children}
                      </h1>
                    ),
                    h2: ({ children }) => (
                      <h2 className="text-2xl font-bold text-purple-300 print:text-purple-700 mt-8 mb-4">
                        {children}
                      </h2>
                    ),
                    h3: ({ children }) => (
                      <h3 className="text-xl font-semibold text-white print:text-black mt-6 mb-3">
                        {children}
                      </h3>
                    ),
                    p: ({ children }) => (
                      <p className="text-gray-300 print:text-gray-700 mb-4 leading-relaxed">
                        {children}
                      </p>
                    ),
                    ul: ({ children }) => (
                      <ul className="list-disc list-inside space-y-2 text-gray-300 print:text-gray-700 mb-4">
                        {children}
                      </ul>
                    ),
                    li: ({ children }) => (
                      <li className="text-gray-300 print:text-gray-700">{children}</li>
                    ),
                    strong: ({ children }) => (
                      <strong className="text-white print:text-black font-semibold">{children}</strong>
                    ),
                    a: ({ href, children }) => (
                      <a href={href} target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:text-purple-300 underline">
                        {children}
                      </a>
                    ),
                  }}
                >
                  {narrative}
                </ReactMarkdown>
              </div>
            </motion.section>
          )}

          {/* Timeline Tab */}
          {activeTab === 'timeline' && (
            <motion.section
              key="timeline"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
            >
              <AdvancedTimelineGraph
                scoutData={scoutData}
                timeline={timeline}
              />
            </motion.section>
          )}

          {/* ── Analysis Tab ─────────────────────────────────── */}
          {activeTab === 'analysis' && (
            <motion.section
              key="analysis"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-6"
            >
              {/* CUI Score breakdown */}
              <div className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/5 p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <span>📐</span>
                  Codebase Understanding Index (CUI v2)
                </h3>
                <div className="flex items-center gap-6 mb-6">
                  <div className="text-center">
                    <div className={`text-6xl font-bold ${cuiScore >= 70 ? 'text-green-400' : cuiScore >= 40 ? 'text-yellow-400' : 'text-red-400'}`}>
                      {cuiScore.toFixed(0)}
                    </div>
                    <div className="text-sm text-gray-400 mt-1">out of 100</div>
                    <div className={`text-sm font-medium mt-1 ${cuiScore >= 70 ? 'text-green-300' : cuiScore >= 40 ? 'text-yellow-300' : 'text-red-300'}`}>
                      {cuiLabel}
                    </div>
                  </div>
                  <div className="flex-1">
                    <div className="bg-slate-800 rounded-full h-4 overflow-hidden mb-2">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${cuiScore}%` }}
                        transition={{ duration: 1 }}
                        className={`h-full rounded-full ${cuiScore >= 70 ? 'bg-gradient-to-r from-green-500 to-emerald-400' : cuiScore >= 40 ? 'bg-gradient-to-r from-yellow-500 to-amber-400' : 'bg-gradient-to-r from-red-500 to-orange-400'}`}
                      />
                    </div>
                    <p className="text-gray-400 text-sm">
                      Higher = easier to understand. Weighted by persona mode.
                    </p>
                  </div>
                </div>
                {Object.keys(cuiComponents).length > 0 && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {Object.entries(cuiComponents).map(([key, val]) => {
                      const labels = {
                        complexity: 'Complexity', file_count: 'File Count', history: 'History',
                        import_complexity: 'Imports', test_coverage: 'Tests', risk_score: 'Risk',
                        bus_factor: 'Bus Factor', documentation: 'Docs',
                      };
                      const pct = Math.round(val * 100);
                      return (
                        <div key={key} className="bg-white/5 rounded-xl p-3">
                          <div className="flex justify-between text-xs text-gray-400 mb-1">
                            <span>{labels[key] || key}</span>
                            <span className={pct >= 70 ? 'text-green-400' : pct >= 40 ? 'text-yellow-400' : 'text-red-400'}>{pct}%</span>
                          </div>
                          <div className="bg-slate-800 rounded-full h-1.5 overflow-hidden">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${pct}%` }}
                              transition={{ duration: 0.8 }}
                              className={`h-full ${pct >= 70 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-500' : 'bg-red-500'}`}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* OCS */}
              <div className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/5 p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <span>🎓</span>
                  Onboarding Complexity Score (OCS)
                </h3>
                <div className="flex items-center gap-6">
                  <div className="text-center">
                    <div className={`text-6xl font-bold ${ocsScore <= 25 ? 'text-green-400' : ocsScore <= 50 ? 'text-yellow-400' : ocsScore <= 75 ? 'text-orange-400' : 'text-red-400'}`}>
                      {ocsScore}
                    </div>
                    <div className={`text-sm font-medium mt-1 ${ocsScore <= 25 ? 'text-green-300' : ocsScore <= 50 ? 'text-yellow-300' : ocsScore <= 75 ? 'text-orange-300' : 'text-red-300'}`}>
                      {ocsLabel}
                    </div>
                  </div>
                  <div className="flex-1">
                    <div className="bg-slate-800 rounded-full h-4 overflow-hidden mb-2">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${ocsScore}%` }}
                        transition={{ duration: 1 }}
                        className={`h-full rounded-full ${ocsScore <= 25 ? 'bg-gradient-to-r from-green-500 to-emerald-400' : ocsScore <= 50 ? 'bg-gradient-to-r from-yellow-500 to-amber-400' : 'bg-gradient-to-r from-orange-500 to-red-400'}`}
                      />
                    </div>
                    <p className="text-gray-400 text-sm">
                      Lower = easier to onboard. Combines file count, complexity, test coverage, and import density.
                    </p>
                  </div>
                </div>
              </div>

              {/* Business Risk */}
              {riskItems.length > 0 && (
                <div className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/5 p-6">
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <span>⚠️</span>
                    Business Risk Assessment
                    <span className="ml-auto text-sm text-gray-400">{businessRisk.total_findings || 0} findings</span>
                  </h3>
                  <div className="space-y-3">
                    {riskItems.slice(0, 10).map((item, i) => (
                      <motion.div
                        key={i}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.05 }}
                        className={`flex items-start gap-3 p-3 rounded-xl border ${
                          item.level === 'CRITICAL' ? 'bg-red-500/10 border-red-500/30' :
                          item.level === 'HIGH' ? 'bg-orange-500/10 border-orange-500/30' :
                          item.level === 'MEDIUM' ? 'bg-yellow-500/10 border-yellow-500/30' :
                          'bg-blue-500/10 border-blue-500/30'
                        }`}
                      >
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full flex-shrink-0 mt-0.5 ${
                          item.level === 'CRITICAL' ? 'bg-red-500/30 text-red-300' :
                          item.level === 'HIGH' ? 'bg-orange-500/30 text-orange-300' :
                          item.level === 'MEDIUM' ? 'bg-yellow-500/30 text-yellow-300' :
                          'bg-blue-500/30 text-blue-300'
                        }`}>{item.level}</span>
                        <div>
                          <div className="text-white text-sm font-medium">{item.name || item.risk_name}</div>
                          {item.file && item.file !== 'repository' && (
                            <div className="text-gray-500 text-xs font-mono mt-0.5">{item.file}</div>
                          )}
                          {item.description && (
                            <div className="text-gray-400 text-xs mt-1">{item.description}</div>
                          )}
                        </div>
                      </motion.div>
                    ))}
                  </div>
                </div>
              )}

              {/* Key Findings */}
              {keyFindings.length > 0 && (
                <div className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/5 p-6">
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <span>🔑</span>
                    Key Findings
                  </h3>
                  <ul className="space-y-2">
                    {keyFindings.map((f, i) => (
                      <motion.li
                        key={i}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.06 }}
                        className="flex items-start gap-3 text-gray-300 text-sm"
                      >
                        <span className="text-purple-400 mt-0.5 flex-shrink-0">▸</span>
                        {f}
                      </motion.li>
                    ))}
                  </ul>
                </div>
              )}

              {/* AI Reasoning */}
              {reasoning.length > 0 && (
                <div className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/5 p-6">
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <span>🤖</span>
                    AI Reasoning Chain
                  </h3>
                  <ol className="space-y-2">
                    {reasoning.map((r, i) => (
                      <li key={i} className="flex items-start gap-3 text-gray-300 text-sm">
                        <span className="text-gray-500 flex-shrink-0 font-mono text-xs mt-0.5 w-5 text-right">{i + 1}.</span>
                        {r}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </motion.section>
          )}

          {/* ── Onboarding Tab ───────────────────────────────── */}
          {activeTab === 'onboarding' && (
            <motion.section
              key="onboarding"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-6"
            >
              {/* Learning path tiers */}
              <div className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/5 p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <span>🗺️</span>
                  Recommended Learning Path
                </h3>
                {Object.keys(learningPath).length > 0 ? (
                  <div className="space-y-4">
                    {[
                      { key: 'day_1', label: 'Day 1', icon: '🌅', color: 'border-green-500/40 bg-green-500/5' },
                      { key: 'week_1', label: 'Week 1', icon: '📅', color: 'border-blue-500/40 bg-blue-500/5' },
                      { key: 'week_2', label: 'Week 2+', icon: '🚀', color: 'border-purple-500/40 bg-purple-500/5' },
                    ].map(({ key, label, icon, color }) => {
                      const files = learningPath[key] || [];
                      if (files.length === 0) return null;
                      return (
                        <div key={key} className={`rounded-xl border p-4 ${color}`}>
                          <div className="flex items-center gap-2 mb-3 font-medium text-white">
                            <span>{icon}</span>
                            {label}
                            <span className="text-xs text-gray-400 ml-auto">{files.length} files</span>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {files.map((f) => (
                              <span key={f} className="text-xs font-mono bg-black/30 text-gray-300 px-2 py-1 rounded-lg">
                                {f}
                              </span>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                    {/* Any other tiers */}
                    {Object.entries(learningPath)
                      .filter(([k]) => !['day_1','week_1','week_2'].includes(k))
                      .map(([key, files]) => (
                        <div key={key} className="rounded-xl border border-gray-500/30 bg-gray-500/5 p-4">
                          <div className="flex items-center gap-2 mb-3 font-medium text-white capitalize">
                            📁 {key.replace(/_/g, ' ')}
                            <span className="text-xs text-gray-400 ml-auto">{files.length} files</span>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {files.map((f) => (
                              <span key={f} className="text-xs font-mono bg-black/30 text-gray-300 px-2 py-1 rounded-lg">{f}</span>
                            ))}
                          </div>
                        </div>
                      ))}
                  </div>
                ) : (
                  <p className="text-gray-400 text-sm py-4">No learning path generated — AST analysis may not have run.</p>
                )}
              </div>

              {/* Safe First PR */}
              <div className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/5 p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <span>🍀</span>
                  Safe First PRs
                </h3>
                {safePR.good_first_issues?.length > 0 ? (
                  <div className="space-y-3">
                    {safePR.good_first_issues.slice(0, 8).map((issue) => (
                      <a
                        key={issue.number}
                        href={issue.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-3 bg-white/5 rounded-xl p-3 hover:bg-white/10 transition border border-white/5 hover:border-green-500/30"
                      >
                        <span className="text-green-400 text-lg">#</span>
                        <div className="flex-1 min-w-0">
                          <div className="text-white text-sm font-medium truncate">{issue.title}</div>
                          <div className="text-gray-500 text-xs">#{issue.number}</div>
                        </div>
                        <span className="text-gray-400 text-sm">→</span>
                      </a>
                    ))}
                  </div>
                ) : (
                  <p className="text-gray-400 text-sm">{safePR.suggestion || 'No tagged good-first-issues found. Explore test files or documentation gaps.'}</p>
                )}
              </div>

              {/* Bus Factor */}
              <div className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/5 p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <span>🚌</span>
                  Bus Factor Analysis
                </h3>
                {Object.keys(busFactor).length > 0 ? (() => {
                  const critical = Object.entries(busFactor).filter(([, v]) => v.critical);
                  const safe = Object.entries(busFactor).filter(([, v]) => !v.critical);
                  return (
                    <>
                      {critical.length > 0 && (
                        <div className="mb-4">
                          <div className="text-red-400 text-sm font-medium mb-2">⚠️ Critical — single-owner files ({critical.length})</div>
                          <div className="space-y-2">
                            {critical.slice(0, 10).map(([file, data]) => (
                              <div key={file} className="flex items-center justify-between bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                                <span className="text-gray-300 text-xs font-mono truncate flex-1 mr-3">{file}</span>
                                <span className="text-red-300 text-xs flex-shrink-0">{data.top_author} — {(data.top_author_pct * 100).toFixed(0)}%</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {safe.length > 0 && (
                        <div className="text-gray-500 text-sm">
                          {safe.length} other files tracked — no single-owner risk
                        </div>
                      )}
                      {critical.length === 0 && (
                        <p className="text-green-400 text-sm">✓ No critical single-owner files detected.</p>
                      )}
                    </>
                  );
                })() : (
                  <p className="text-gray-400 text-sm">Bus factor data unavailable.</p>
                )}
              </div>
            </motion.section>
          )}

          {/* Contributors Tab */}
          {activeTab === 'contributors' && (            <motion.section
              key="contributors"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/5 p-6 md:p-8"
            >
              <h2 className="text-2xl font-bold text-white mb-8 flex items-center gap-3">
                <span>👥</span>
                Contributor Profiles
              </h2>

              {scoutData.top_contributors?.length > 0 ? (
                <div className="grid gap-4 md:grid-cols-2">
                  {scoutData.top_contributors.slice(0, 6).map((contributor, index) => {
                    // Handle different data formats (Git Analytics vs GitHub API)
                    const name = contributor.name || contributor.username || 'Unknown';
                    const commits = contributor.commit_count || contributor.contributions || 0;

                    // Calculate percentage if missing
                    let percentage = contributor.percentage;
                    if (percentage === undefined || percentage === null) {
                      const total = scoutData.total_commits || 1;
                      percentage = (commits / total) * 100;
                    }

                    const impactLevel = percentage > 30 ? 'Lead Developer' :
                      percentage > 15 ? 'Core Contributor' : 'Contributor';
                    const impactColor = percentage > 30 ? 'text-purple-400' :
                      percentage > 15 ? 'text-blue-400' : 'text-gray-400';

                    return (
                      <motion.div
                        key={name}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.1 }}
                        whileHover={{ scale: 1.02 }}
                        className="bg-white/5 rounded-xl p-5 border border-white/5"
                      >
                        <div className="flex items-center gap-4">
                          {contributor.avatar_url ? (
                            <img
                              src={contributor.avatar_url}
                              alt={name}
                              className="w-14 h-14 rounded-full border-2 border-purple-500/30"
                            />
                          ) : (
                            <div className="w-14 h-14 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-2xl font-bold text-white">
                              {name.charAt(0).toUpperCase()}
                            </div>
                          )}
                          <div className="flex-1">
                            <h3 className="font-semibold text-white text-lg">{name}</h3>
                            <a
                              href={contributor.profile_url || `https://github.com/${name}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className={`text-sm ${impactColor} hover:underline`}
                            >
                              {impactLevel}
                            </a>
                          </div>
                        </div>

                        <div className="mt-4">
                          <div className="flex justify-between text-sm mb-2">
                            <span className="text-gray-400">Contributions</span>
                            <span className="text-white">{commits} commits</span>
                          </div>
                          <div className="bg-slate-800 rounded-full h-2 overflow-hidden">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${Math.min(percentage, 100)}%` }}
                              transition={{ duration: 1, delay: index * 0.1 }}
                              className="h-full bg-gradient-to-r from-purple-500 to-pink-500"
                            />
                          </div>
                          <div className="text-right text-xs text-gray-500 mt-1">
                            {percentage.toFixed(1)}% of total
                          </div>
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center text-gray-400 py-12">
                  <div className="text-4xl mb-4">👤</div>
                  <p>No contributor data available.</p>
                </div>
              )}
            </motion.section>
          )}

          {/* GitHub Insights Tab */}
          {activeTab === 'github' && (
            <motion.section
              key="github"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-6"
            >
              {scoutData.github_data?.available ? (
                <>
                  {/* Repository Stats */}
                  <div className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/5 p-6">
                    <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                      <span>📊</span>
                      Repository Statistics
                    </h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {[
                        { label: 'Stars', value: scoutData.github_data.repo_info?.stars?.toLocaleString() || 0, icon: '⭐' },
                        { label: 'Forks', value: scoutData.github_data.repo_info?.forks?.toLocaleString() || 0, icon: '🍴' },
                        { label: 'Watchers', value: scoutData.github_data.repo_info?.watchers?.toLocaleString() || 0, icon: '👁️' },
                        { label: 'Open Issues', value: scoutData.github_data.repo_info?.open_issues?.toLocaleString() || 0, icon: '🐛' },
                      ].map((stat) => (
                        <div key={stat.label} className="bg-white/5 rounded-xl p-4 text-center">
                          <div className="text-2xl mb-1">{stat.icon}</div>
                          <div className="text-2xl font-bold text-white">{stat.value}</div>
                          <div className="text-sm text-gray-400">{stat.label}</div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Languages */}
                  {scoutData.github_data.languages && (
                    <div className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/5 p-6">
                      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                        <span>💻</span>
                        Languages
                      </h3>
                      <div className="space-y-3">
                        {Object.entries(scoutData.github_data.languages.breakdown || {})
                          .sort(([, a], [, b]) => b - a)
                          .slice(0, 8)
                          .map(([lang, percentage], i) => (
                            <div key={lang}>
                              <div className="flex justify-between text-sm mb-1">
                                <span className="text-white">{lang}</span>
                                <span className="text-gray-400">{percentage}%</span>
                              </div>
                              <div className="bg-slate-800 rounded-full h-2 overflow-hidden">
                                <motion.div
                                  initial={{ width: 0 }}
                                  animate={{ width: `${percentage}%` }}
                                  transition={{ duration: 0.8, delay: i * 0.1 }}
                                  className={`h-full ${i === 0 ? 'bg-gradient-to-r from-purple-500 to-pink-500' :
                                    i === 1 ? 'bg-gradient-to-r from-blue-500 to-cyan-500' :
                                      i === 2 ? 'bg-gradient-to-r from-green-500 to-emerald-500' :
                                        'bg-gradient-to-r from-gray-500 to-gray-400'
                                    }`}
                                />
                              </div>
                            </div>
                          ))}
                      </div>
                    </div>
                  )}

                  {/* Releases */}
                  {scoutData.github_data.releases && scoutData.github_data.releases.length > 0 && (
                    <div className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/5 p-6">
                      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                        <span>🚀</span>
                        Recent Releases
                      </h3>
                      <div className="space-y-3">
                        {scoutData.github_data.releases.slice(0, 5).map((release, i) => (
                          <motion.div
                            key={release.tag}
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.1 }}
                            className="flex items-center justify-between bg-white/5 rounded-lg p-3"
                          >
                            <div className="flex items-center gap-3">
                              <span className="text-xl">{release.is_prerelease ? '🔬' : '📦'}</span>
                              <div>
                                <div className="text-white font-medium">{release.tag}</div>
                                {release.name && <div className="text-sm text-gray-400">{release.name}</div>}
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="text-sm text-gray-400">
                                {formatDate(release.published_at)}
                              </div>
                              {release.download_count > 0 && (
                                <div className="text-xs text-gray-500">
                                  {release.download_count.toLocaleString()} downloads
                                </div>
                              )}
                            </div>
                          </motion.div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Community Health */}
                  {scoutData.github_data.community_health && (
                    <div className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/5 p-6">
                      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                        <span>🏥</span>
                        Community Health
                      </h3>
                      <div className="mb-4">
                        <div className="flex justify-between text-sm mb-2">
                          <span className="text-gray-400">Health Score</span>
                          <span className="text-white font-bold">
                            {scoutData.github_data.community_health.health_percentage}%
                          </span>
                        </div>
                        <div className="bg-slate-800 rounded-full h-3 overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${scoutData.github_data.community_health.health_percentage}%` }}
                            className={`h-full ${scoutData.github_data.community_health.health_percentage >= 80
                              ? 'bg-green-500'
                              : scoutData.github_data.community_health.health_percentage >= 50
                                ? 'bg-yellow-500'
                                : 'bg-red-500'
                              }`}
                          />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                        {[
                          { label: 'README', has: scoutData.github_data.community_health.has_readme },
                          { label: 'License', has: scoutData.github_data.community_health.has_license },
                          { label: 'Contributing', has: scoutData.github_data.community_health.has_contributing },
                          { label: 'Code of Conduct', has: scoutData.github_data.community_health.has_code_of_conduct },
                          { label: 'Issue Template', has: scoutData.github_data.community_health.has_issue_template },
                          { label: 'PR Template', has: scoutData.github_data.community_health.has_pull_request_template },
                        ].map((item) => (
                          <div
                            key={item.label}
                            className={`flex items-center gap-2 px-3 py-2 rounded-lg ${item.has ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
                              }`}
                          >
                            <span>{item.has ? '✓' : '✕'}</span>
                            <span className="text-sm">{item.label}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Repo Info */}
                  {scoutData.github_data.repo_info && (
                    <div className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/5 p-6">
                      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                        <span>ℹ️</span>
                        Repository Info
                      </h3>
                      <div className="space-y-3">
                        {scoutData.github_data.repo_info.description && (
                          <div>
                            <span className="text-gray-400 text-sm">Description</span>
                            <p className="text-white mt-1">{scoutData.github_data.repo_info.description}</p>
                          </div>
                        )}
                        {scoutData.github_data.repo_info.topics?.length > 0 && (
                          <div>
                            <span className="text-gray-400 text-sm">Topics</span>
                            <div className="flex flex-wrap gap-2 mt-2">
                              {scoutData.github_data.repo_info.topics.map((topic) => (
                                <span
                                  key={topic}
                                  className="px-3 py-1 bg-purple-500/20 text-purple-300 rounded-full text-sm"
                                >
                                  {topic}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        <div className="grid grid-cols-2 gap-3 pt-2">
                          {scoutData.github_data.repo_info.license && (
                            <div className="bg-white/5 rounded-lg p-3">
                              <span className="text-gray-400 text-xs">License</span>
                              <div className="text-white mt-1">{scoutData.github_data.repo_info.license}</div>
                            </div>
                          )}
                          <div className="bg-white/5 rounded-lg p-3">
                            <span className="text-gray-400 text-xs">Size</span>
                            <div className="text-white mt-1">
                              {(scoutData.github_data.repo_info.size_kb / 1024).toFixed(1)} MB
                            </div>
                          </div>
                        </div>
                        {scoutData.github_data.repo_info.is_archived && (
                          <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3 mt-3">
                            <span className="text-yellow-400">⚠️ This repository is archived</span>
                          </div>
                        )}
                        {scoutData.github_data.repo_info.is_fork && (
                          <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3">
                            <span className="text-blue-400">
                              🍴 Fork of {scoutData.github_data.repo_info.parent_repo}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center text-gray-400 py-12 bg-black/40 backdrop-blur-xl rounded-2xl border border-white/5">
                  <div className="text-4xl mb-4">🐙</div>
                  <p>GitHub API data not available.</p>
                  <p className="text-sm mt-2">Add GITHUB_TOKEN to your .env file for enriched insights.</p>
                </div>
              )}
            </motion.section>
          )}

          {/* Sources Tab */}
          {activeTab === 'sources' && (
            <motion.section
              key="sources"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="bg-black/40 backdrop-blur-xl rounded-2xl border border-white/5 p-6 md:p-8"
            >
              <h2 className="text-2xl font-bold text-white mb-8 flex items-center gap-3">
                <span>📚</span>
                External Sources & Citations
              </h2>

              {citations.length > 0 ? (
                <div className="space-y-4">
                  {citations.map((citation, index) => (
                    <motion.a
                      key={index}
                      href={citation.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.1 }}
                      whileHover={{ scale: 1.01, x: 5 }}
                      className="block bg-white/5 rounded-xl p-5 border border-white/5 hover:border-purple-500/30 transition-all"
                    >
                      <div className="flex items-start gap-4">
                        <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center text-purple-400 font-bold flex-shrink-0">
                          [{citation.number}]
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="font-semibold text-white mb-1 truncate">{citation.title}</h3>
                          <p className="text-sm text-gray-400 mb-2 line-clamp-2">{citation.snippet}</p>
                          <div className="flex items-center gap-2 text-xs text-purple-400">
                            <span>🔗</span>
                            <span className="truncate">{citation.url}</span>
                          </div>
                        </div>
                        <span className="text-gray-400 text-xl">→</span>
                      </div>
                    </motion.a>
                  ))}
                </div>
              ) : (
                <div className="text-center text-gray-400 py-12">
                  <div className="text-4xl mb-4">📭</div>
                  <p>No external sources were cited in this investigation.</p>
                  <p className="text-sm mt-2">This report was generated using git history analysis only.</p>
                </div>
              )}
            </motion.section>
          )}
        </AnimatePresence>

        {/* Footer Actions */}
        <div className="mt-8 flex justify-center gap-4 print:hidden">
          <Link
            to={`/dashboard/${id}`}
            className="px-6 py-3 bg-white/5 hover:bg-white/10 text-white rounded-lg border border-white/10 transition"
          >
            📊 View Dashboard
          </Link>
          <Link
            to="/"
            className="px-6 py-3 bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition"
          >
            🏛️ New Investigation
          </Link>
        </div>
      </main>

      {/* Print Footer */}
      <footer className="hidden print:block text-center py-8 border-t border-gray-200 mt-8">
        <p className="text-gray-500">Generated by Neural Archaeologist • {new Date().toLocaleDateString()}</p>
      </footer>
    </div>
  );
}

export default Report;