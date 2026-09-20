import Foundation

public struct DuressMappingEntry: Codable, Equatable {
    public let code: String
    public let accountId: Int64

    public init(code: String, accountId: Int64) {
        self.code = code
        self.accountId = accountId
    }
}

private let duressMappingPath: String = {
    let paths = NSSearchPathForDirectoriesInDomains(.libraryDirectory, .userDomainMask, true)
    let base = paths.first ?? NSTemporaryDirectory()
    return base + "/duress_accounts.json"
}()

public func loadDuressMappings() -> [DuressMappingEntry] {
    guard let data = try? Data(contentsOf: URL(fileURLWithPath: duressMappingPath)) else {
        return []
    }
    return (try? JSONDecoder().decode([DuressMappingEntry].self, from: data)) ?? []
}

public func saveDuressMappings(_ entries: [DuressMappingEntry]) {
    guard let data = try? JSONEncoder().encode(entries) else {
        return
    }
    try? data.write(to: URL(fileURLWithPath: duressMappingPath), options: .atomic)
}

public func setDuressMapping(code: String, accountId: Int64) {
    var entries = loadDuressMappings()
    entries.removeAll { $0.code == code || $0.accountId == accountId }
    entries.append(DuressMappingEntry(code: code, accountId: accountId))
    saveDuressMappings(entries)
}

public func removeDuressMapping(accountId: Int64) {
    var entries = loadDuressMappings()
    entries.removeAll { $0.accountId == accountId }
    saveDuressMappings(entries)
}

public func isDuressModeConfigured() -> Bool {
    return !loadDuressMappings().isEmpty
}

// Implemented by SharedAccountContext so PasscodeEntryController (which has no
// direct reference to it) can trigger an account switch without threading a
// closure through multiple existing initializers.
public protocol DuressAccountSwitching: AnyObject {
    func duressSwitchToAccount(id: Int64)
}

public final class DuressSwitchingRegistry {
    public static weak var current: DuressAccountSwitching?
}
