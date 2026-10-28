# Solo si el proyecto de iOS se arma con CocoaPods (por defecto Alcancía usa Swift Package Manager).
require 'json'
package = JSON.parse(File.read(File.join(__dir__, 'package.json')))
Pod::Spec.new do |s|
  s.name = 'AlcanciaCarpeta'
  s.version = package['version']
  s.summary = package['description']
  s.license = package['license']
  s.homepage = 'https://github.com/alcancia-app/alcancia'
  s.author = 'Alcancía'
  s.source = { :git => 'https://github.com/alcancia-app/alcancia.git', :tag => s.version.to_s }
  s.source_files = 'ios/Sources/**/*.swift'
  s.ios.deployment_target = '14.0'
  s.dependency 'Capacitor'
  s.swift_version = '5.9'
end
